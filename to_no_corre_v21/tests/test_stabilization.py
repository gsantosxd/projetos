import json
import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import app


class StabilizationTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "cidades_presencial": ["Vitória", "Vila Velha"],
            "estado_local": "ES",
            "idade_maxima_vaga_dias": 60,
            "descartar_vagas_encerradas": True,
            "descartar_vagas_exclusivas_pcd": True,
            "descartar_superior_completo_obrigatorio": True,
            "descartar_experiencia_especifica_anos": 5,
        }

    def test_profile_has_no_minimum_salary_rules(self):
        with open(app.PROFILE_PATH, encoding="utf-8") as stream:
            profile = json.load(stream)
        forbidden = {
            "salario_minimo_vaga", "bolsa_minima_estagio",
            "pretensao_salarial_padrao", "filtrar_por_salario",
            "salario_preferido_minimo",
        }
        self.assertFalse(forbidden.intersection(profile))

    def test_first_run_creates_neutral_profile_without_personal_searches(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,"perfil.json")
            with patch.object(app,"PROFILE_PATH",path):profile=app.load_profile()
            self.assertTrue(os.path.isfile(path))
            self.assertEqual([],profile["consultas_gupy"])
            self.assertEqual([],profile["consultas_linkedin"])
            self.assertEqual([],profile["cidades_presencial"])
            self.assertFalse(profile["mostrar_compativeis_fora_regiao"])

    def test_first_run_cannot_search_without_resume(self):
        instance=object.__new__(app.App);instance.search_running=False
        instance.info=unittest.mock.Mock();instance.edit_profile=unittest.mock.Mock()
        with patch.object(app,"read_cv",return_value=""),patch.object(app.messagebox,"showinfo") as notice:
            app.App.start_source(instance,"all")
        notice.assert_called_once();instance.edit_profile.assert_called_once()

    def test_resume_readers_support_pdf_docx_and_txt(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as directory:
            text="Currículo de teste com formação, experiência e habilidades. " * 3
            txt_path=os.path.join(directory,"curriculo.txt")
            with open(txt_path,"w",encoding="utf-8") as stream:stream.write(text)
            self.assertGreater(len(app.parse_cv_file(txt_path)),80)
            path = os.path.join(directory, "curriculo.docx")
            document = Document()
            document.add_paragraph(text)
            document.save(path)
            self.assertGreater(len(app.parse_cv_file(path)), 80)
            page=unittest.mock.Mock();page.extract_text.return_value=text
            with patch("pypdf.PdfReader",return_value=unittest.mock.Mock(pages=[page])):
                self.assertGreater(len(app.parse_cv_file(os.path.join(directory,"curriculo.pdf"))),80)

    def test_remote_scope_must_include_brazil(self):
        accepted = app.location_decision({
            "local": "Worldwide", "workplace_type": "remote", "source_brazil": False
        }, self.profile)
        rejected = app.location_decision({
            "local": "United States only", "workplace_type": "remote", "source_brazil": False
        }, self.profile)
        self.assertTrue(accepted["ok"])
        self.assertFalse(rejected["ok"])

    def test_remote_search_hint_is_never_modality_evidence(self):
        result = app.location_decision({
            "local": "Brazil", "remote": True, "search_remote_hint": True,
            "workplace_type": "", "source_brazil": True,
        }, self.profile)
        self.assertEqual("Verificar modelo", result["mode"])
        self.assertEqual("Baixa", result["confidence"])

    def test_linkedin_remote_search_result_stays_unconfirmed_if_page_fails(self):
        html = """
        <li><a class='base-card__full-link' href='https://linkedin.test/jobs/1?x=1'></a>
        <h3 class='base-search-card__title'>Assistente</h3>
        <h4 class='base-search-card__subtitle'>Empresa</h4>
        <span class='job-search-card__location'>Remote</span></li>
        """
        profile={"consultas_linkedin":["assistente"],"cidades_presencial":["Vitória"],"estado_local":"ES"}
        with patch.object(app,"linkedin_search_html",return_value=html), \
             patch.object(app,"generic_job_from_url",side_effect=RuntimeError("página indisponível")), \
             patch.object(app.time,"sleep",return_value=None):
            jobs=app.fetch_linkedin(profile)
        self.assertEqual(1,len(jobs))
        self.assertTrue(jobs[0]["search_remote_hint"])
        self.assertEqual("",jobs[0]["workplace_type"])
        self.assertEqual("Verificar modelo",app.location_decision(jobs[0],self.profile)["mode"])

    def test_linkedin_fast_phase_does_not_wait_for_individual_details(self):
        html = """
        <li><a class='base-card__full-link' href='https://linkedin.test/jobs/view/vaga-123456'></a>
        <h3 class='base-search-card__title'>Vaga rápida</h3>
        <h4 class='base-search-card__subtitle'>Empresa</h4>
        <span class='job-search-card__location'>Brazil</span></li>
        """
        profile={"consultas_linkedin":["vaga"],"cidades_presencial":["Vitória"],
                 "enriquecimento_inicial_linkedin":0,"enriquecer_somente_se_necessario":False}
        with patch.object(app,"linkedin_search_html",return_value=html), \
             patch.object(app,"generic_job_from_url") as detail,patch.object(app.time,"sleep",return_value=None):
            jobs=app.fetch_linkedin(profile)
        self.assertEqual(1,len(jobs));detail.assert_not_called()

    def test_linkedin_search_uses_second_page_without_duplicating_cards(self):
        first="""<li><a class='base-card__full-link' href='https://linkedin.test/jobs/view/a-123456'></a>
        <h3 class='base-search-card__title'>Assistente A</h3></li>"""
        second="""<li><a class='base-card__full-link' href='https://linkedin.test/jobs/view/b-234567'></a>
        <h3 class='base-search-card__title'>Assistente B</h3></li>"""
        def page(_q,_remote,_location,start=0):return first if start==0 else second
        profile={"consultas_linkedin":["assistente"],"cidades_presencial":["Vitória"],"estado_local":"ES"}
        with patch.object(app,"linkedin_search_html",side_effect=page) as search,patch.object(app.time,"sleep",return_value=None):
            jobs=app.fetch_linkedin(profile)
        self.assertEqual(2,len(jobs));self.assertEqual(4,search.call_count)

    def test_complete_collection_uses_all_twelve_sources(self):
        instance=object.__new__(app.App);instance.p={"buscar_vagas_internacionais":True,"nivel_ingles":"Fluente",
            "_disable_persistent_source_cache":True};instance.after=lambda _delay,callback:callback()
        class Info:
            def set(self,_value):pass
        instance.info=Info()
        def job(name,source):return [{"titulo":name,"empresa":source,"local":"Brazil","url":f"https://{source}/{name}","fonte":source}]
        with patch.object(app,"fetch_gupy",return_value=job("Gupy job","Gupy")) as gupy, \
             patch.object(app,"fetch_linkedin",return_value=job("LinkedIn job","LinkedIn")) as linkedin, \
             patch.object(app,"fetch_google",side_effect=[job("Google job","Google"),job("Indeed job","Indeed/Google"),
                                                          job("Hitmarker job","Hitmarker/Google"),job("Games BR job","Vagas em Games/Google")]) as google, \
             patch.object(app,"fetch_remotive",return_value=job("Remote job","Remotive")) as remote, \
             patch.object(app,"fetch_jobicy",return_value=job("Jobicy job","Jobicy")) as jobicy, \
             patch.object(app,"fetch_himalayas",return_value=job("Himalayas job","Himalayas")) as himalayas, \
             patch.object(app,"fetch_remote_landers",return_value=job("Landers job","Remote Landers")) as landers, \
             patch.object(app,"fetch_remote_game_jobs",return_value=job("RGJ job","Remote Game Jobs")) as rgj, \
             patch.object(app,"fetch_work_with_indies",return_value=job("Indie job","Work With Indies")) as indies:
            result=app.App.collect(instance,"all")
        self.assertEqual(12,len(result));gupy.assert_called_once();linkedin.assert_called_once();remote.assert_called_once()
        jobicy.assert_called_once();himalayas.assert_called_once();landers.assert_called_once()
        rgj.assert_called_once();indies.assert_called_once()
        self.assertEqual(4,google.call_count)
        self.assertEqual(12,len(instance.last_source_counts))

    def test_portuguese_resume_keeps_international_search_disabled(self):
        profile=app.default_profile()
        resume=("Experiência profissional com atendimento ao cliente e rotinas administrativas. "
                "Formação superior e habilidades com contratos, documentos e planilhas. "
                "Responsabilidades de suporte e organização do trabalho.")
        app.adapt_profile_to_cv(profile,resume)
        self.assertEqual("Português",profile["idioma_curriculo_detectado"])
        self.assertFalse(profile["buscar_vagas_internacionais"])
        self.assertEqual([],profile["consultas_ingles"])
        self.assertFalse(any("jobs Brazil" in query for query in profile["consultas_google"]))

    def test_domestic_collection_skips_international_sources(self):
        instance=object.__new__(app.App);instance.p={"buscar_vagas_internacionais":False};instance.after=lambda _d,cb:cb()
        instance.info=unittest.mock.Mock()
        job=lambda name,source:[{"titulo":name,"empresa":source,"local":"Brasil",
                                "url":f"https://{source}/{name}","fonte":source}]
        with patch.object(app,"fetch_gupy",return_value=job("Gupy","Gupy")), \
             patch.object(app,"fetch_linkedin",return_value=job("LinkedIn","LinkedIn")), \
             patch.object(app,"fetch_google",side_effect=[job("Google","Google"),job("Indeed","Indeed/Google"),
                                                          job("Games","Vagas em Games/Google")]) as google, \
             patch.object(app,"fetch_remotive") as international:
            result=app.App.collect(instance,"all")
        self.assertEqual(5,len(result));self.assertEqual(3,google.call_count);international.assert_not_called()

    def test_reset_for_new_user_removes_personal_state_and_keeps_database_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            instance=object.__new__(app.App);instance.search_running=False
            instance.conn=app.connect_database(os.path.join(directory,"vagas.db"));app.App.db(instance)
            instance.conn.execute("INSERT INTO vagas(titulo,url) VALUES('Vaga','https://vaga/1')")
            instance.conn.execute("INSERT INTO preferencias_feedback(termo,positivo) VALUES('excel',1)")
            instance.conn.commit()
            cv_path=os.path.join(directory,"curriculo.txt");cache_path=os.path.join(directory,"cache_detalhes.json")
            profile_path=os.path.join(directory,"perfil.json");backup_dir=os.path.join(directory,"backups")
            log_path=os.path.join(directory,"to_no_corre.log");browser_dir=os.path.join(directory,"browser_profiles")
            os.makedirs(backup_dir);open(os.path.join(backup_dir,"vagas.db"),"w").close()
            os.makedirs(browser_dir);open(os.path.join(browser_dir,"cookies.bin"),"w").close()
            open(log_path,"w").close()
            with open(cv_path,"w",encoding="utf-8") as stream:stream.write("dados pessoais")
            with open(cache_path,"w",encoding="utf-8") as stream:stream.write("{}")
            instance.q=unittest.mock.Mock();instance.view_mode=unittest.mock.Mock();instance.batch_selection={1}
            instance.refresh=unittest.mock.Mock();instance.info=unittest.mock.Mock();instance.after=unittest.mock.Mock()
            with patch.object(app,"BASE_DIR",directory),patch.object(app,"CV_PATH",cv_path), \
                 patch.object(app,"CACHE_PATH",cache_path),patch.object(app,"PROFILE_PATH",profile_path), \
                 patch.object(app,"BACKUP_DIR",backup_dir),patch.object(app,"LOG_PATH",log_path), \
                 patch.object(app.messagebox,"askyesno",return_value=True), \
                 patch.object(app.messagebox,"showinfo"),patch.object(app.messagebox,"showerror") as error:
                self.assertTrue(app.App.reset_for_new_user(instance))
                error.assert_not_called()
            self.assertEqual(0,instance.conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
            self.assertEqual(0,instance.conn.execute("SELECT COUNT(*) FROM preferencias_feedback").fetchone()[0])
            self.assertFalse(os.path.exists(cv_path));self.assertFalse(os.path.exists(cache_path))
            self.assertFalse(os.path.exists(backup_dir))
            self.assertFalse(os.path.exists(browser_dir))
            self.assertTrue(os.path.exists(log_path));self.assertEqual(0,os.path.getsize(log_path))
            with open(profile_path,encoding="utf-8") as stream:profile=json.load(stream)
            self.assertEqual([],profile["consultas_gupy"])
            instance.conn.close()
            for handler in list(app.logging.getLogger().handlers):
                handler.close();app.logging.getLogger().removeHandler(handler)
            app.logging.basicConfig(filename=app.LOG_PATH,level=app.logging.INFO,
                format="%(asctime)s %(levelname)s %(message)s",encoding="utf-8",force=True)

    def test_privacy_notice_acceptance_is_versioned_in_local_database(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn;app.App.db(instance)
        self.assertFalse(app.App.privacy_notice_accepted(instance))
        app.App.meta_set(instance,"aviso_privacidade_versao",app.PRIVACY_NOTICE_VERSION)
        self.assertTrue(app.App.privacy_notice_accepted(instance))
        conn.close()

    def test_pcd_preference_requires_specific_recorded_confirmation(self):
        instance=object.__new__(app.App);instance.p=app.default_profile()
        self.assertFalse(app.App.pcd_consent_valid(instance))
        instance.p["consentimento_pcd_versao"]=app.PCD_CONSENT_VERSION
        instance.p["consentimento_pcd_em"]="2026-09-03T12:00:00+00:00"
        self.assertTrue(app.App.pcd_consent_valid(instance))

    def test_data_directory_protection_is_not_applied_to_source_workspace(self):
        with patch.object(app.sys,"frozen",False,create=True),patch.object(app.subprocess,"run") as run:
            self.assertFalse(app.protect_local_data_directory())
            run.assert_not_called()

    def test_build_uses_stable_data_directory_and_knows_last_beta(self):
        self.assertEqual("Data",app.APP_DATA_VERSION)
        self.assertIn("Beta0_9_0",app.LEGACY_APP_DATA_VERSIONS)
        self.assertEqual("0.9.1-beta",app.APP_VERSION)

    def test_legacy_data_migration_copies_without_deleting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy=os.path.join(directory,"Beta0_9_0");current=os.path.join(directory,"Data")
            os.makedirs(legacy);os.makedirs(current)
            legacy_db=os.path.join(legacy,"vagas.db")
            conn=sqlite3.connect(legacy_db);conn.execute("CREATE TABLE dados(valor TEXT)")
            conn.execute("INSERT INTO dados VALUES('preservado')");conn.commit();conn.close()
            with open(os.path.join(legacy,"perfil.json"),"w",encoding="utf-8") as stream:json.dump({"teste":1},stream)
            with patch.object(app.sys,"frozen",True,create=True),patch.object(app,"APP_DATA_ROOT",directory),\
                 patch.object(app,"BASE_DIR",current),patch.object(app,"DB_PATH",os.path.join(current,"vagas.db")),\
                 patch.object(app,"LEGACY_APP_DATA_VERSIONS",("Beta0_9_0",)):
                self.assertTrue(app.migrate_legacy_data_directory())
                self.assertFalse(app.migrate_legacy_data_directory())
            copied=sqlite3.connect(os.path.join(current,"vagas.db"))
            self.assertEqual(("preservado",),copied.execute("SELECT valor FROM dados").fetchone());copied.close()
            self.assertTrue(os.path.isfile(legacy_db))
            self.assertTrue(os.path.isfile(os.path.join(legacy,"perfil.json")))

    def test_distribution_spec_does_not_bundle_personal_runtime_files(self):
        root=os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root,"ToNoCorre.spec"),encoding="utf-8") as stream:spec=stream.read().lower()
        for personal in ("curriculo.pdf","curriculo.txt","perfil.json","vagas.db","cache_detalhes.json"):
            self.assertNotIn(personal,spec)
        self.assertIn('version="version_info.txt"',spec)

    def test_runtime_dependencies_are_exactly_pinned(self):
        root=os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root,"requirements.txt"),encoding="utf-8") as stream:
            lines=[line.strip() for line in stream if line.strip() and not line.startswith("#")]
        self.assertTrue(lines)
        self.assertTrue(all("==" in line for line in lines))

    def test_personal_runtime_files_are_ignored_by_version_control(self):
        root=os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root,".gitignore"),encoding="utf-8") as stream:ignored=stream.read()
        for personal in ("perfil.json","curriculo.txt","curriculo_original.*","vagas.db","browser_profiles/","backups/"):
            self.assertIn(personal,ignored)

    def test_privacy_notice_describes_local_storage_external_sources_and_deletion(self):
        notice=app.norm(app.PRIVACY_NOTICE)
        for expected in ("neste computador","comunicacoes externas","pcd","limpar tudo","nao ha servidor"):
            self.assertIn(expected,notice)

    def test_english_resume_is_recorded_as_fluent_english(self):
        profile=app.default_profile()
        resume=("Professional experience and responsibilities with customer support and project management. "
                "Education: bachelor degree. Skills include Microsoft Office and data analysis.")
        summary=app.adapt_profile_to_cv(profile,resume)
        self.assertEqual("Inglês",profile["idioma_curriculo_detectado"])
        self.assertIn("Inglês fluente",summary["skills"])
        self.assertIn("Inglês fluente",profile["competencias_perfil"])

    def test_mixed_resume_is_not_automatically_considered_fluent(self):
        profile=app.default_profile()
        resume="Professional experience with atendimento de clientes, formação e skills."
        summary=app.adapt_profile_to_cv(profile,resume)
        self.assertNotEqual("Inglês",profile["idioma_curriculo_detectado"])
        self.assertNotIn("Inglês fluente",summary["skills"])

    def test_jobicy_maps_structured_remote_location(self):
        payload={"jobs":[{"jobTitle":"Legal Assistant","companyName":"Example","jobGeo":"Worldwide",
                           "jobDescription":"<p>Fluent English and contracts</p>","url":"https://jobicy.test/1",
                           "pubDate":datetime.now().strftime("%Y-%m-%d"),"salaryMin":1000,"salaryMax":2000,
                           "salaryCurrency":"USD","salaryPeriod":"year"}]}
        with patch.object(app,"cached_source_json",return_value=payload):jobs=app.fetch_jobicy(self.profile)
        self.assertEqual(1,len(jobs));self.assertEqual("remote",jobs[0]["workplace_type"])
        self.assertEqual("Worldwide",jobs[0]["applicant_location_requirements"])
        self.assertTrue(app.location_decision(jobs[0],self.profile)["ok"])

    def test_jobicy_uses_english_profile_queries_and_deduplicates(self):
        item={"jobTitle":"Legal Assistant","companyName":"Example","jobGeo":"Anywhere",
              "jobDescription":"Contracts","url":"https://jobicy.test/same",
              "pubDate":datetime.now().strftime("%Y-%m-%d")}
        profile=dict(self.profile);profile["consultas_ingles"]=["legal assistant","paralegal"]
        with patch.object(app,"cached_source_json",side_effect=[{"jobs":[item]},{"jobs":[item]}]) as api:
            jobs=app.fetch_jobicy(profile)
        self.assertEqual(1,len(jobs));self.assertEqual(2,api.call_count)
        self.assertEqual({"legal assistant","paralegal"},{call.args[2]["tag"] for call in api.call_args_list})

    def test_fluent_english_requirement_accepts_english_resume_profile(self):
        profile=dict(self.profile);profile["competencias_perfil"]=["Inglês fluente"]
        job={"titulo":"Customer Support","descricao":"Fluent English is required"}
        self.assertEqual("",app.mandatory_blocker(job,profile))
        profile["competencias_perfil"]=[]
        self.assertEqual("inglês fluente obrigatório",app.mandatory_blocker(job,profile))

    def test_english_requirement_respects_declared_proficiency(self):
        intermediate_job={"titulo":"Customer Support","descricao":"Intermediate English required"}
        fluent_job={"titulo":"Customer Support","descricao":"Advanced English required"}
        self.assertEqual("",app.mandatory_blocker(intermediate_job,{"nivel_ingles":"Intermediário"}))
        self.assertEqual("exige inglês intermediário obrigatório",
                         app.mandatory_blocker(intermediate_job,{"nivel_ingles":"Básico"}))
        self.assertEqual("inglês fluente obrigatório",
                         app.mandatory_blocker(fluent_job,{"nivel_ingles":"Intermediário"}))
        self.assertEqual("",app.mandatory_blocker(fluent_job,{"nivel_ingles":"Fluente"}))

    def test_regulated_social_worker_role_is_blocked_without_matching_degree(self):
        profile={"cursos_curriculo_detectados":["direito","analise e desenvolvimento de sistemas"]}
        job={"titulo":"Assistente Social","descricao":"Atendimento ao público em Vitória"}
        self.assertEqual("profissão exige formação em Serviço Social",app.mandatory_blocker(job,profile))
        matching={"cursos_curriculo_detectados":["serviço social"]}
        self.assertEqual("",app.mandatory_blocker(job,matching))

    def test_generic_process_word_does_not_become_legal_skill(self):
        summary=app.cv_profile_summary(
            "Professional responsibilities include improving the customer support process and systems.")
        self.assertNotIn("Processos jurídicos",summary["skills"])

    def test_games_rss_maps_role_company_location_and_date(self):
        xml="""<rss><channel><item>
        <title>Studio Example is hiring a QA Tester to work from Anywhere</title>
        <link>https://games.test/job/1</link><pubDate>Wed, 02 Sep 2099 00:00:00 GMT</pubDate>
        <description>English game testing and customer support.</description>
        </item></channel></rss>"""
        with patch.object(app,"cached_source_text",return_value=xml):
            jobs=app.fetch_games_rss(self.profile,"https://games.test/feed","Games Test")
        self.assertEqual(1,len(jobs));self.assertEqual("QA Tester",jobs[0]["titulo"])
        self.assertEqual("Studio Example",jobs[0]["empresa"]);self.assertEqual("Anywhere",jobs[0]["local"])
        self.assertEqual("2099-09-02",jobs[0]["data_publicacao"])
        self.assertTrue(app.location_decision(jobs[0],self.profile)["ok"])

    def test_himalayas_maps_worldwide_job_and_uses_english_query(self):
        now=int(datetime.now().timestamp())
        payload={"jobs":[{"title":"Legal Assistant","companyName":"Example","locationRestrictions":[],
                           "description":"<p>Contracts and fluent English</p>","applicationLink":"https://himalayas.test/1",
                           "pubDate":now,"expiryDate":now+86400,"minSalary":1000,"maxSalary":2000,
                           "currency":"USD","salaryPeriod":"monthly"}]}
        profile=dict(self.profile);profile["consultas_ingles"]=["legal assistant"]
        with patch.object(app,"cached_source_json",return_value=payload) as api:jobs=app.fetch_himalayas(profile)
        self.assertEqual(1,len(jobs));self.assertEqual("Worldwide",jobs[0]["local"])
        self.assertEqual("legal assistant",api.call_args.args[2]["q"])
        self.assertTrue(app.location_decision(jobs[0],self.profile)["ok"])

    def test_remote_landers_keeps_location_restriction_for_filtering(self):
        payload={"jobs":[{"title":"Support Specialist","company":"Example","category":"Support",
                           "subtags":["Customer Support"],"location":"United States","type":"Full-time",
                           "level":"Entry-level","salary":"$50k","postedDate":datetime.now().strftime("%Y-%m-%d"),
                           "url":"https://remotelanders.test/1","applyUrl":"https://ats.test/1"}]}
        with patch.object(app,"cached_source_json",return_value=payload):jobs=app.fetch_remote_landers(self.profile)
        self.assertEqual(1,len(jobs));self.assertEqual("United States",jobs[0]["applicant_location_requirements"])
        self.assertFalse(app.location_decision(jobs[0],self.profile)["ok"])

    def test_unknown_modality_always_uses_verify_model(self):
        for job in [
            {"local": "Vitória, ES"},
            {"local": "Não informado"},
            {"local": "Brazil", "search_remote_hint": True},
        ]:
            with self.subTest(job=job):
                self.assertEqual("Verificar modelo", app.location_decision(job, self.profile)["mode"])
        outside=app.location_decision({"local":"São Paulo, SP"},self.profile)
        self.assertFalse(outside["ok"]);self.assertIn("fora da região",outside["mode"])
        self.assertEqual("Verificar modelo", app.simple_location_mode("", "Verificar modelo"))

    def test_linkedin_uses_full_state_name_to_avoid_es_as_spain(self):
        html="""<li><a href='https://linkedin.test/jobs/view/a-123456'></a>
        <h3 class='base-search-card__title'>Assistente</h3></li>"""
        profile={"consultas_linkedin":["assistente"],"cidades_presencial":["Vitória"],"estado_local":"ES"}
        locations=[]
        def page(_q,_remote,location,start=0):locations.append(location);return html if start==0 else ""
        with patch.object(app,"linkedin_search_html",side_effect=page),patch.object(app.time,"sleep",return_value=None):
            app.fetch_linkedin(profile)
        self.assertIn("Vitoria, Espirito Santo, Brazil",locations)

    def test_unknown_modality_explains_why_it_needs_review(self):
        missing=app.location_decision({"local":"Vitória, ES","descricao":""},self.profile)
        described=app.location_decision({"local":"Vitória, ES","descricao":"Rotinas administrativas"},self.profile)
        self.assertEqual("Verificar modelo",missing["mode"])
        self.assertIn("descrição e modalidade ausentes",missing["evidence"])
        self.assertIn("não declara a modalidade",described["evidence"])

    def test_structured_modes_require_compatible_location(self):
        remote = app.location_decision({"local": "Brazil", "workplace_type": "remote"}, self.profile)
        onsite = app.location_decision({"local": "Vitória, ES", "workplace_type": "onsite"}, self.profile)
        hybrid = app.location_decision({"local": "Vila Velha, ES", "workplace_type": "hybrid"}, self.profile)
        outside = app.location_decision({"local": "São Paulo, SP", "workplace_type": "hybrid"}, self.profile)
        self.assertEqual("Remoto Brasil — confirmado", remote["mode"])
        self.assertEqual("Presencial — confirmado", onsite["mode"])
        self.assertEqual("Híbrido — confirmado", hybrid["mode"])
        self.assertFalse(outside["ok"])

    def test_city_and_state_match_is_exact_not_prefix(self):
        profile=dict(self.profile)
        vitoria=app.location_decision({"local":"Vitória, ES","workplace_type":"onsite"},profile)
        conquista=app.location_decision({"local":"Vitória da Conquista, BA","workplace_type":"onsite"},profile)
        self.assertTrue(vitoria["ok"])
        self.assertFalse(conquista["ok"])

    def test_city_filter_is_accent_insensitive_in_both_directions(self):
        job_accented={"local":"São Paulo, SP","workplace_type":"onsite"}
        job_plain={"local":"Sao Paulo, SP","workplace_type":"onsite"}
        plain_profile={"cidades_presencial":["sao paulo"],"estado_local":"SP"}
        accented_profile={"cidades_presencial":["São Paulo"],"estado_local":"SP"}
        self.assertTrue(app.location_decision(job_accented,plain_profile)["ok"])
        self.assertTrue(app.location_decision(job_plain,accented_profile)["ok"])

    def test_linkedin_location_query_is_identical_with_or_without_accent(self):
        calls=[]
        def search(_query,_remote,location,start=0):
            calls.append(location);return ""
        base={"consultas_linkedin":["auxiliar"],"estado_local":"SP"}
        with patch.object(app,"linkedin_search_html",side_effect=search):
            app.fetch_linkedin(dict(base,cidades_presencial=["São Paulo"]))
            accented=list(calls);calls.clear()
            app.fetch_linkedin(dict(base,cidades_presencial=["sao paulo"]))
        self.assertEqual(accented,calls)
        self.assertIn("Sao Paulo, Sao Paulo, Brazil",calls)

    def test_linkedin_uses_primary_city_to_avoid_excessive_requests(self):
        locations=[]
        def search(_query,_remote,location,start=0):locations.append(location);return ""
        profile={"consultas_linkedin":["auxiliar"],"cidades_presencial":["Cariacica","Vitória","Serra"],
                 "estado_local":"ES"}
        with patch.object(app,"linkedin_search_html",side_effect=search):app.fetch_linkedin(profile)
        self.assertIn("Cariacica, Espirito Santo, Brazil",locations)
        self.assertEqual({"Brazil","Cariacica, Espirito Santo, Brazil"},set(locations))

    def test_city_requires_configured_state(self):
        profile=dict(self.profile);profile["cidades_presencial"]=["Vitória"]
        self.assertFalse(app.location_decision(
            {"local":"Vitória, BA","workplace_type":"onsite"},profile)["ok"])

    def test_excluded_location_matches_city_state_country_but_not_similar_city(self):
        profile=dict(self.profile);profile["localidades_excluidas"]=["São Paulo/SP","United States"]
        self.assertEqual("São Paulo/SP",app.excluded_location_reason({"local":"São Paulo, SP"},profile))
        self.assertEqual("United States",app.excluded_location_reason({"local":"United States only"},profile))
        self.assertEqual("",app.excluded_location_reason({"local":"São Paulo do Potengi, RN"},profile))
        self.assertEqual("",app.excluded_location_reason({"local":"Worldwide"},profile))

    def test_excluded_location_is_a_reversible_named_hard_filter(self):
        profile=dict(self.profile);profile["localidades_excluidas"]=["Rio de Janeiro/RJ"]
        job={"titulo":"Assistente","local":"Rio de Janeiro, RJ","workplace_type":"onsite",
             "data_publicacao":datetime.now().strftime("%Y-%m-%d")}
        allowed,reason=app.hard_filter(job,profile)
        self.assertFalse(allowed);self.assertEqual(
            "localidade excluída pelo usuário — Rio de Janeiro/RJ",reason)

    def test_remote_without_brazil_scope_is_not_home_office(self):
        result = app.location_decision({"local": "Remote", "workplace_type": "remote"}, self.profile)
        self.assertEqual("Verificar modelo", result["mode"])
        self.assertNotIn("Home office", app.simple_location_mode("Remote", result["mode"]))

    def test_structured_gupy_remote_is_eligible_for_brazil_without_text_location(self):
        gupy=app.location_decision(
            {"local":"Não informado","fonte":"Gupy","workplace_type":"remote"},self.profile)
        linkedin=app.location_decision(
            {"local":"Não informado","fonte":"LinkedIn","workplace_type":"remote"},self.profile)
        self.assertEqual("Remoto Brasil — confirmado",gupy["mode"])
        self.assertEqual("Verificar modelo",linkedin["mode"])

    def test_confirmed_home_office_and_remote_share_remote_label(self):
        self.assertEqual("Remoto",app.simple_location_mode("Brazil","Remoto Brasil — confirmado"))
        self.assertEqual("São Paulo, SP • Remoto",
                         app.simple_location_mode("São Paulo, SP","Remoto Brasil — confirmado"))

    def test_explicit_description_can_confirm_each_mode(self):
        remote = app.location_decision({"local": "Brazil", "descricao": "Modelo de trabalho remoto"}, self.profile)
        onsite = app.location_decision({"local": "Vitória, ES", "descricao": "Trabalho 100% presencial"}, self.profile)
        hybrid = app.location_decision({"local": "Vila Velha, ES", "descricao": "Modelo híbrido"}, self.profile)
        self.assertTrue(remote["mode"].startswith("Remoto Brasil"))
        self.assertTrue(onsite["mode"].startswith("Presencial"))
        self.assertTrue(hybrid["mode"].startswith("Híbrido"))

    def test_conflicting_modality_requires_review(self):
        result = app.location_decision({
            "local": "Vitória, ES", "descricao": "Modelo híbrido e trabalho 100% remoto"
        }, self.profile)
        self.assertEqual("Verificar modelo", result["mode"])
        self.assertEqual("Baixa", result["confidence"])

    def test_home_office_benefit_does_not_define_remote(self):
        result = app.location_decision({
            "local": "Vitória, ES", "descricao": "Auxílio home office e vale-refeição"
        }, self.profile)
        self.assertNotIn("Remoto Brasil", result["mode"])

    def test_assistant_to_coordinator_is_not_senior(self):
        job = {"titulo": "Assistente do Coordenador", "descricao": "Rotinas administrativas"}
        self.assertEqual("", app.mandatory_blocker(job, self.profile))

    def test_company_age_is_not_experience_requirement(self):
        job = {"titulo": "Assistente", "descricao": "Empresa com 50 anos de experiência no mercado"}
        self.assertEqual("", app.mandatory_blocker(job, self.profile))

    def test_publication_date_has_simple_brazilian_format(self):
        self.assertEqual("30/08/2026",app.format_date_br("2026-08-30T12:45:00Z"))
        self.assertEqual("Data não informada",app.format_date_br(""))

    def test_jobs_query_returns_publication_date_without_changing_core_indexes(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("""INSERT INTO vagas(titulo,empresa,url,status,decisao,data_publicacao)
                        VALUES('Vaga','Empresa','https://vaga/data','Nova','APROVADA','2026-08-30')""")
        sql,params=app.jobs_query("todas","");row=conn.execute(sql,params).fetchone()
        self.assertEqual("Vaga",row[2]);self.assertEqual("2026-08-30",row[9])
        conn.close()

    def test_dedupe_preserves_seniority_but_ignores_safe_company_suffixes(self):
        junior={"titulo":"Analista Júnior - Remoto","empresa":"Empresa Ltda.","local":"Brasil"}
        pleno={"titulo":"Analista Pleno - Remoto","empresa":"Empresa","local":"Brasil"}
        duplicate={"titulo":"Analista Júnior","empresa":"Empresa","local":"Brasil"}
        self.assertNotEqual(app.job_fingerprint(junior),app.job_fingerprint(pleno))
        self.assertEqual(app.job_fingerprint(junior),app.job_fingerprint(duplicate))

    def test_recent_publication_has_small_explainable_bonus(self):
        base={"titulo":"Assistente","descricao":"Rotinas administrativas","local":"Vitória, ES"}
        recent=dict(base,data_publicacao=datetime.now().date().isoformat())
        old=dict(base,data_publicacao=(datetime.now().date()-timedelta(days=30)).isoformat())
        recent_score,_label,reason,_mode=app.score_job(recent,self.profile,"")
        old_score=app.score_job(old,self.profile,"")[0]
        self.assertGreater(recent_score,old_score)
        self.assertIn("Publicação recente",reason)

    def test_expired_valid_through_is_closed_only_after_deadline(self):
        yesterday=(datetime.now().date()-timedelta(days=1)).isoformat()
        tomorrow=(datetime.now().date()+timedelta(days=1)).isoformat()
        self.assertTrue(app.expired_job_reason({"valid_through":yesterday}))
        self.assertEqual("",app.expired_job_reason({"valid_through":tomorrow}))

    def test_database_backup_creates_recoverable_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            database=os.path.join(directory,"vagas.db");backup_dir=os.path.join(directory,"backups")
            conn=sqlite3.connect(database);conn.execute("CREATE TABLE dados(valor TEXT)")
            conn.execute("INSERT INTO dados VALUES('preservado')");conn.commit();conn.close()
            with patch.object(app,"DB_PATH",database),patch.object(app,"BACKUP_DIR",backup_dir):
                backup=app.backup_database()
            copied=sqlite3.connect(backup)
            self.assertEqual(("preservado",),copied.execute("SELECT valor FROM dados").fetchone())
            copied.close()

    def test_database_backup_includes_committed_wal_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database=os.path.join(directory,"vagas.db");backup_dir=os.path.join(directory,"backups")
            conn=sqlite3.connect(database);conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE dados(valor TEXT)");conn.commit()
            conn.execute("INSERT INTO dados VALUES('ainda no wal')");conn.commit()
            with patch.object(app,"DB_PATH",database),patch.object(app,"BACKUP_DIR",backup_dir):
                backup=app.backup_database()
            copied=sqlite3.connect(backup)
            self.assertEqual(("ainda no wal",),copied.execute("SELECT valor FROM dados").fetchone())
            copied.close();conn.close()

    def test_json_save_is_atomic_and_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target=os.path.join(directory,"perfil.json")
            app.save_json_file(target,{"nome":"Usuário"})
            with open(target,encoding="utf-8") as stream:self.assertEqual("Usuário",json.load(stream)["nome"])
            self.assertEqual(["perfil.json"],os.listdir(directory))

    def test_background_workers_are_tracked_and_not_daemon(self):
        instance=object.__new__(app.App);instance.worker_threads=set();instance.worker_lock=threading.Lock()
        release=threading.Event();started=threading.Event()
        def work():started.set();release.wait(2)
        worker=app.App.start_worker(instance,work,name="teste-worker")
        self.assertTrue(started.wait(1));self.assertFalse(worker.daemon)
        with instance.worker_lock:self.assertIn(worker,instance.worker_threads)
        release.set();worker.join(2)
        with instance.worker_lock:self.assertNotIn(worker,instance.worker_threads)

    def test_database_connection_uses_wal_timeout_and_serialized_transactions(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,"threadsafe.db");conn=app.connect_database(path)
            conn.execute("CREATE TABLE counter(value INTEGER)");conn.execute("INSERT INTO counter VALUES(0)");conn.commit()
            def increment():
                for _ in range(25):
                    with conn:conn.execute("UPDATE counter SET value=value+1")
            workers=[threading.Thread(target=increment) for _ in range(4)]
            for worker in workers:worker.start()
            for worker in workers:worker.join()
            self.assertEqual("wal",conn.execute("PRAGMA journal_mode").fetchone()[0].lower())
            self.assertEqual(8000,conn.execute("PRAGMA busy_timeout").fetchone()[0])
            self.assertEqual(100,conn.execute("SELECT value FROM counter").fetchone()[0]);conn.close()

    def test_feedback_is_explainable_and_limited_in_score(self):
        profile=dict(self.profile)
        profile["feedback_preferencias"]={"ambiental":20}
        score,_label,reason,_mode=app.score_job(
            {"titulo":"Assistente ambiental","descricao":"Rotinas ambientais","local":"Vitória, ES"},profile,"")
        self.assertIn("Preferências +",reason)
        self.assertLessEqual(score,100)

    def test_discarded_curriculum_compatibility_uses_main_score_without_mutation(self):
        job={"titulo":"Assistente Administrativo","descricao":"Atendimento, Excel e rotinas administrativas",
             "local":"Vitória, ES","status":"Ignorada"}
        original=dict(job)
        score=app.curriculum_compatibility(job,self.profile,"Experiência com atendimento e Excel")
        self.assertIsInstance(score,int);self.assertGreaterEqual(score,0);self.assertLessEqual(score,100)
        self.assertEqual(original,job)

    def test_internships_follow_user_preference(self):
        job={"titulo":"Estágio administrativo","descricao":"Estudante de administração","local":"Vitória, ES"}
        disabled=dict(self.profile,buscar_estagios=False)
        enabled=dict(self.profile,buscar_estagios=True)
        self.assertEqual((False,"estágio desativado pelo usuário"),app.hard_filter(job,disabled))
        self.assertNotEqual("estágio desativado pelo usuário",app.hard_filter(job,enabled)[1])

    def test_disabled_internships_are_removed_from_existing_results_but_not_queue(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn;instance.p=dict(self.profile,buscar_estagios=False)
        instance.cv="";instance.refresh=lambda:None;app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(1,'Estágio em TI','https://vaga/1','Nova',0)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(2,'Estágio na fila','https://vaga/2','Nova',1)")
        self.assertEqual(1,app.App.apply_internship_preference(instance,False))
        self.assertEqual(('Ignorada',0),conn.execute("SELECT status,selecionada_lote FROM vagas WHERE id=1").fetchone())
        self.assertEqual(('Nova',1),conn.execute("SELECT status,selecionada_lote FROM vagas WHERE id=2").fetchone())
        conn.close()

    def test_enabled_internships_move_existing_vacancy_from_another_course(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        instance.p={"cursos_curriculo_detectados":["direito"],"buscar_estagios":True}
        instance.cv="";instance.refresh=lambda:None;app.App.db(instance)
        conn.execute("""INSERT INTO vagas(id,titulo,descricao,url,status,selecionada_lote)
                        VALUES(1,'Estágio em Administração','','https://vaga/admin','Nova',0)""")
        conn.execute("""INSERT INTO vagas(id,titulo,descricao,url,status,selecionada_lote)
                        VALUES(2,'Estágio em Direito','','https://vaga/direito','Nova',0)""")
        self.assertEqual(1,app.App.apply_internship_preference(instance,True))
        self.assertEqual('Ignorada',conn.execute("SELECT status FROM vagas WHERE id=1").fetchone()[0])
        self.assertEqual('Nova',conn.execute("SELECT status FROM vagas WHERE id=2").fetchone()[0])
        conn.close()

    def test_enrichment_restores_only_auto_filtered_confirmed_remote(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn;instance.p=self.profile
        instance.refresh=lambda:None;app.App.db(instance)
        conn.execute("""INSERT INTO vagas(id,titulo,empresa,local,descricao,url,fonte,workplace_type,status)
                        VALUES(1,'Remota','Empresa','Brazil','Trabalho totalmente remoto','https://vaga/1','LinkedIn','remote','Ignorada')""")
        conn.execute("""INSERT INTO descartadas(titulo,url,motivo_descarte)
                        VALUES('Remota','https://vaga/1','Local fora da região — remoto não confirmado')""")
        self.assertTrue(app.App.restore_auto_filtered_remote(instance,1))
        self.assertEqual('Nova',conn.execute("SELECT status FROM vagas WHERE id=1").fetchone()[0])
        self.assertEqual(0,conn.execute("SELECT COUNT(*) FROM descartadas").fetchone()[0]);conn.close()

    def test_separate_outside_region_preserves_queue_and_moves_only_visible_jobs(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn;instance.p=self.profile
        instance.refresh=lambda:None;app.App.db(instance)
        conn.execute("""INSERT INTO vagas(id,titulo,empresa,local,descricao,url,workplace_type,status,selecionada_lote)
                        VALUES(1,'Externa','Empresa','São Paulo, SP','Trabalho presencial','https://vaga/1','onsite','Nova',0)""")
        conn.execute("""INSERT INTO vagas(id,titulo,empresa,local,descricao,url,workplace_type,status,selecionada_lote)
                        VALUES(2,'Na fila','Empresa','São Paulo, SP','Trabalho presencial','https://vaga/2','onsite','Nova',1)""")
        self.assertEqual(1,app.App.separate_outside_region_jobs(instance))
        self.assertEqual(('Ignorada',0),conn.execute("SELECT status,selecionada_lote FROM vagas WHERE id=1").fetchone())
        self.assertEqual(('Nova',1),conn.execute("SELECT status,selecionada_lote FROM vagas WHERE id=2").fetchone())
        self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM descartadas").fetchone()[0]);conn.close()

    def test_queue_feedback_is_persisted_without_changing_job(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn;instance.p={}
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status) VALUES(1,'Analista Ambiental','https://vaga/1','Nova')")
        app.App.record_feedback(instance,1,True)
        self.assertGreater(conn.execute("SELECT SUM(positivo) FROM preferencias_feedback").fetchone()[0],0)
        self.assertEqual(("Analista Ambiental","Nova"),conn.execute("SELECT titulo,status FROM vagas WHERE id=1").fetchone())
        conn.close()

    def test_deduplication_merges_sources(self):
        jobs = [
            {"titulo": "Assistente", "empresa": "Empresa A", "local": "Vitória, ES", "url": "https://a/1", "fonte": "Gupy"},
            {"titulo": "Assistente", "empresa": "Empresa A", "local": "Vitória, ES", "url": "https://b/2", "fonte": "LinkedIn"},
        ]
        result = app.dedupe_multisource(jobs, self.profile)
        self.assertEqual(1, len(result))
        self.assertIn("Gupy", result[0]["fontes_encontradas"])
        self.assertIn("LinkedIn", result[0]["fontes_encontradas"])

    def test_database_migration_preserves_existing_row(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE vagas(id INTEGER PRIMARY KEY, titulo TEXT, empresa TEXT, local TEXT, modalidade TEXT, descricao TEXT, url TEXT UNIQUE, fonte TEXT, data_publicacao TEXT, salario TEXT, score INTEGER, classificacao TEXT, motivo TEXT, status TEXT DEFAULT 'Nova', criada_em TEXT DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO vagas(titulo,empresa,local,url) VALUES('Vaga antiga','Empresa','Vitória','https://vaga')")
        conn.execute("CREATE TABLE descartadas(id INTEGER PRIMARY KEY, titulo TEXT, empresa TEXT, local TEXT, descricao TEXT, url TEXT UNIQUE, fonte TEXT, data_publicacao TEXT, salario TEXT, motivo_descarte TEXT, descartada_em TEXT DEFAULT CURRENT_TIMESTAMP, workplace_type TEXT DEFAULT '', applicant_location_requirements TEXT DEFAULT '', structured_location_json TEXT DEFAULT '')")
        instance = object.__new__(app.App)
        instance.conn = conn
        app.App.db(instance)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(vagas)")}
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        self.assertTrue({
            "workplace_type", "location_confidence", "location_evidence",
            "workplace_type_raw", "workplace_source", "structured_location_json",
            "applicant_location_requirements", "remote_eligible_brazil", "modality_checked_at",
        }.issubset(columns))
        conn.close()

    def test_cv_profile_builds_generic_terms_and_courses(self):
        text=("Graduação em Engenharia Ambiental. Experiência com licenciamento ambiental, "
              "relatórios ambientais, Excel e atendimento a clientes. Licenciamento ambiental.")
        profile={}
        summary=app.adapt_profile_to_cv(profile,text)
        self.assertIn("licenciamento",summary["keywords"])
        self.assertTrue(profile["termos_perfil"])
        self.assertEqual(4,profile["perfil_curriculo_versao"])
        self.assertTrue(any("engenharia ambiental" in query.lower() for query in profile["consultas_br"]))

    def test_profile_v2_preserves_good_queries_and_removes_malformed_courses(self):
        profile={"consultas_gupy":["assistente de contratos","estágio • ensino medio completo certificacoes e cursos"],
                 "consultas_linkedin":["controller jurídico"],"motores_busca":{}}
        text="Graduação em Direito - 7º período\nEnsino médio completo\nCertificações e cursos"
        summary=app.adapt_profile_to_cv(profile,text)
        self.assertEqual(["direito"],summary["courses"])
        self.assertIn("assistente de contratos",profile["consultas_gupy"])
        self.assertIn("controller jurídico",profile["consultas_linkedin"])
        self.assertFalse(any("•" in query or "período" in query.lower() for query in profile["consultas_gupy"]))

    def test_high_school_only_resume_suggests_but_does_not_force_entry_search(self):
        profile=app.default_profile()
        resume="Ensino médio completo. Busco meu primeiro emprego e ainda não possuo experiência profissional."
        app.adapt_profile_to_cv(profile,resume)
        self.assertTrue(profile["perfil_inicio_carreira_detectado"])
        self.assertFalse(profile["perfil_inicio_carreira"])
        queries={app.norm(query) for query in profile["consultas_gupy"]}
        self.assertNotIn("operador de caixa",queries)
        self.assertFalse(profile["buscar_vagas_internacionais"])

    def test_selected_entry_market_search_adds_balanced_job_families(self):
        profile=app.default_profile();profile["buscar_vagas_inicio_carreira"]=True
        resume="Ensino médio completo. Busco meu primeiro emprego e não possuo experiência profissional."
        app.adapt_profile_to_cv(profile,resume)
        self.assertTrue(profile["perfil_inicio_carreira"])
        queries={app.norm(query) for query in profile["consultas_gupy"]}
        for expected in ("operador de caixa","auxiliar de logistica","estoquista",
                         "auxiliar de producao","auxiliar de servicos gerais"):
            self.assertIn(expected,queries)

    def test_gupy_search_is_scoped_to_allowed_state_and_keeps_national_remote(self):
        profile={"consultas_gupy":["auxiliar"],"estado_local":"ES","aceita_remoto":True}
        calls=[]
        def fake_json_get(_url,params):
            calls.append(dict(params));return {"data":[]}
        with patch("app.json_get",side_effect=fake_json_get):
            app.fetch_gupy(profile)
        self.assertTrue(any(call.get("state")=="Espírito Santo" for call in calls))
        self.assertTrue(any(call.get("workplaceType")=="remote" and "state" not in call
                            for call in calls))

    def test_gupy_keeps_national_discovery_but_skips_remote_scope_when_remote_is_disabled(self):
        profile={"consultas_gupy":["auxiliar"],"estado_local":"ES","aceitar_remoto":False}
        calls=[]
        with patch("app.json_get",side_effect=lambda _url,params:(calls.append(dict(params)) or {"data":[]})):
            app.fetch_gupy(profile)
        self.assertTrue(calls)
        self.assertTrue(any(call.get("state")=="Espírito Santo" for call in calls))
        self.assertTrue(any("state" not in call and "workplaceType" not in call for call in calls))
        self.assertFalse(any("workplaceType" in call for call in calls))

    def test_gupy_checks_second_national_and_remote_pages(self):
        profile={"consultas_gupy":["assistente"],"estado_local":"ES","aceitar_remoto":True,
                 "enriquecer_somente_se_necessario":False}
        calls=[]
        def response(_url,params):
            calls.append(dict(params))
            if params["offset"]==100:return {"data":[]}
            return {"data":[{"id":index,"name":f"Assistente {index}",
                              "jobUrl":f"https://gupy.test/{params.get('state','br')}/{params.get('workplaceType','all')}/{index}"}
                             for index in range(100)]}
        with patch("app.json_get",side_effect=response):app.fetch_gupy(profile)
        self.assertTrue(any(call.get("offset")==100 and "state" not in call and "workplaceType" not in call
                            for call in calls))
        self.assertTrue(any(call.get("offset")==100 and call.get("workplaceType")=="remote"
                            for call in calls))

    def test_gupy_distributes_result_limit_across_profile_queries(self):
        profile={"consultas_gupy":["jurídico","suporte","administrativo","atendimento"],
                 "estado_local":"ES","aceitar_remoto":True,"max_resultados_por_fonte":24,
                 "enriquecer_somente_se_necessario":False}
        calls=[]
        def response(_url,params):
            calls.append(dict(params))
            query=params["jobName"]
            return {"data":[{"id":f"{query}-{index}","name":f"{query} {index}",
                              "jobUrl":f"https://gupy.test/{query}/{params.get('state','br')}/{params.get('workplaceType','all')}/{index}"}
                             for index in range(100)]}
        with patch("app.json_get",side_effect=response):
            jobs=app.fetch_gupy(profile)
        searched={call["jobName"] for call in calls}
        self.assertEqual(set(profile["consultas_gupy"]),searched)
        self.assertLessEqual(len(jobs),24)
        self.assertEqual(set(profile["consultas_gupy"]),
                         {job["titulo"].rsplit(" ",1)[0] for job in jobs})

    def test_persistent_source_cache_reuses_results_during_safe_interval(self):
        profile={"consultas_gupy":["assistente"],"estado_local":"ES"}
        job={"titulo":"Assistente","empresa":"Empresa","local":"Vitória, ES",
             "url":"https://vaga/cache","fonte":"Gupy","data_publicacao":""}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(app,"SOURCE_RESULTS_PATH",os.path.join(directory,"fontes.json")), \
             patch.object(app,"SOURCE_RESULTS_CACHE",{"version":1,"entries":{}}), \
             patch.object(app,"SOURCE_RESULT_METRICS",{}):
            fetch=unittest.mock.Mock(return_value=[job])
            first=app.persistent_source_fetch("Gupy",profile,fetch,cooldown_seconds=3600)
            second=app.persistent_source_fetch("Gupy",profile,fetch,cooldown_seconds=3600)
        self.assertEqual(1,fetch.call_count)
        self.assertEqual(first,second)

    def test_persistent_source_cache_falls_back_when_source_fails(self):
        profile={"consultas_linkedin":["assistente"],"estado_local":"ES"}
        job={"titulo":"Assistente","empresa":"Empresa","local":"Vitória, ES",
             "url":"https://vaga/fallback","fonte":"LinkedIn","data_publicacao":""}
        key=app.source_search_signature("LinkedIn",profile)
        cache={"version":1,"entries":{key:{"updated_at":0,"source":"LinkedIn","jobs":[job]}}}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(app,"SOURCE_RESULTS_PATH",os.path.join(directory,"fontes.json")), \
             patch.object(app,"SOURCE_RESULTS_CACHE",cache),patch.object(app,"SOURCE_RESULT_METRICS",{}):
            result=app.persistent_source_fetch(
                "LinkedIn",profile,unittest.mock.Mock(side_effect=RuntimeError("limitado")),cooldown_seconds=60)
        self.assertEqual([job],result)

    def test_gupy_daily_rotation_keeps_top_results_and_changes_exploration(self):
        profile={"consultas_gupy":["jurídico","suporte","administrativo","atendimento"],
                 "estado_local":"ES","aceitar_remoto":True,"max_resultados_por_fonte":24,
                 "enriquecer_somente_se_necessario":False}
        def response(_url,params):
            query=params["jobName"]
            return {"data":[{"id":f"{query}-{index}","name":f"{query} {index}",
                              "jobUrl":f"https://gupy.test/{query}/{params.get('state','br')}/{params.get('workplaceType','all')}/{index}"}
                             for index in range(100)]}
        with patch.object(app,"json_get",side_effect=response),patch.object(app,"date") as clock:
            clock.today.return_value=datetime(2026,9,3).date();first=app.fetch_gupy(profile)
            clock.today.return_value=datetime(2026,9,4).date();second=app.fetch_gupy(profile)
        first_urls={job["url"] for job in first};second_urls={job["url"] for job in second}
        self.assertNotEqual(first_urls,second_urls)
        self.assertTrue(any(url.endswith("/0") for url in first_urls & second_urls))

    def test_young_apprentice_search_is_separate_and_opt_in(self):
        profile=app.default_profile();profile["buscar_jovem_aprendiz"]=True
        app.adapt_profile_to_cv(profile,"Ensino médio completo. Busco oportunidade de trabalho.")
        queries={app.norm(query) for query in profile["consultas_gupy"]}
        self.assertIn("jovem aprendiz",queries)
        self.assertIn("aprendiz administrativo",queries)
        self.assertNotIn("operador de caixa",queries)

    def test_young_apprentice_queries_are_prioritized_before_general_roles(self):
        profile=app.default_profile();profile["buscar_jovem_aprendiz"]=True
        profile["buscar_vagas_inicio_carreira"]=True
        app.adapt_profile_to_cv(profile,"Ensino médio completo. Primeiro emprego, sem experiência.")
        queries=[app.norm(query) for query in profile["consultas_gupy"]]
        self.assertEqual("jovem aprendiz",queries[0])
        self.assertLess(queries.index("aprendiz administrativo"),queries.index("operador de caixa"))

    def test_apprentice_view_only_lists_apprentice_titles(self):
        sql,params=app.jobs_query("aprendiz")
        self.assertEqual([],params)
        self.assertIn("lower(titulo) LIKE '%aprendiz%'",sql)

    def test_apprentice_vacancy_is_blocked_when_option_is_disabled(self):
        job={"titulo":"Jovem Aprendiz Administrativo","descricao":"Ensino médio completo",
             "local":"Vitória, ES","workplace_type":"onsite"}
        profile=dict(self.profile);profile["buscar_jovem_aprendiz"]=False
        accepted,reason=app.hard_filter(job,profile)
        self.assertFalse(accepted);self.assertEqual("Jovem Aprendiz desativado pelo usuário",reason)
        profile["buscar_jovem_aprendiz"]=True
        self.assertTrue(app.hard_filter(job,profile)[0])

    def test_entry_search_expands_google_queries_with_experience_phrases(self):
        profile=app.default_profile();profile["buscar_vagas_inicio_carreira"]=True
        app.adapt_profile_to_cv(profile,"Ensino médio completo. Não possuo experiência profissional.")
        self.assertEqual(20,len(profile["consultas_google"]))
        joined=" ".join(profile["consultas_google"]).lower()
        self.assertIn("sem experiência",joined)
        self.assertIn("não exige experiência",joined)
        self.assertGreater(len(profile["consultas_linkedin"]),35)

    def test_entry_google_queries_are_distributed_across_allowed_cities(self):
        profile=app.default_profile();profile["buscar_vagas_inicio_carreira"]=True
        profile["cidades_presencial"]=["Cariacica","Vitória","Vila Velha"];profile["estado_local"]="ES"
        app.adapt_profile_to_cv(profile,"Ensino médio completo. Não possuo experiência profissional.")
        joined=" ".join(profile["consultas_google"])
        self.assertIn('"Cariacica ES"',joined)
        self.assertIn('"Vitoria ES"',joined)
        self.assertIn('"Vila Velha ES"',joined)

    def test_entry_profile_prioritizes_no_experience_high_school_vacancy(self):
        profile=app.default_profile();profile["perfil_inicio_carreira"]=True
        job={"titulo":"Auxiliar de Loja","descricao":"Ensino médio completo. Não exige experiência.",
             "local":"Vitória, ES","workplace_type":"onsite"}
        profile["cidades_presencial"]=["Vitória"];profile["estado_local"]="ES"
        score,label,reason,_mode=app.score_job(job,profile,"Ensino médio completo")
        self.assertGreaterEqual(score,70)
        self.assertIn("Cargo de entrada +25",reason)
        self.assertIn(label,("Boa","Excelente"))

    def test_professional_history_does_not_activate_entry_profile_automatically(self):
        profile=app.default_profile()
        resume=("Ensino médio completo. Experiência profissional em atendimento ao cliente, "
                "rotinas administrativas, caixa e organização de documentos.")
        app.adapt_profile_to_cv(profile,resume)
        self.assertFalse(profile["perfil_inicio_carreira"])

    def test_generic_internship_uses_course_from_resume(self):
        profile={"cursos_curriculo_detectados":["engenharia ambiental"]}
        compatible={"titulo":"Estágio em Engenharia Ambiental","descricao":"Estudantes de Engenharia Ambiental"}
        outside={"titulo":"Estágio em Marketing","descricao":"Cursando graduação em Marketing"}
        self.assertEqual("OK_PERFIL",app.internship_course_status(compatible,profile))
        self.assertEqual("FORA",app.internship_course_status(outside,profile))

    def test_explicit_internship_course_in_title_is_filtered_without_description(self):
        profile={"cursos_curriculo_detectados":["direito"]}
        for title in ("Estágio em Administração","Estágio Jornalismo","Pessoa Estagiária em Marketing",
                      "Estágio Contábil-Financeiro","Estágio Técnico em Segurança do Trabalho",
                      "Pessoa Estagiária em Atração e Seleção","Estágio em Geoprocessamento"):
            job={"titulo":title,"descricao":""}
            self.assertTrue(app.is_intern(job),title)
            self.assertEqual("FORA",app.internship_course_status(job,profile),title)
        self.assertEqual("OK_PERFIL",app.internship_course_status(
            {"titulo":"Estágio em Direito","descricao":""},profile))

    def test_generic_internship_without_declared_course_remains_for_review(self):
        profile={"cursos_curriculo_detectados":["direito"]}
        self.assertEqual("REVISAR",app.internship_course_status(
            {"titulo":"Programa de Estágio","descricao":"Oportunidade inicial."},profile))

    def test_course_matrix_extracts_searches_and_matches_multiple_education_areas(self):
        cases=[
            ("Graduação em Administração - 4º semestre","administracao","Estágio em Administração"),
            ("Bacharelado em Ciências Contábeis | 3º período","ciencias contabeis","Estágio em Contabilidade"),
            ("Cursando Psicologia","psicologia","Estágio em Psicologia"),
            ("Curso superior de Enfermagem - em andamento","enfermagem","Estágio em Enfermagem"),
            ("Engenharia Civil - cursando","engenharia civil","Estágio em Engenharia Civil"),
            ("Formação acadêmica: Marketing","marketing","Pessoa Estagiária em Marketing"),
            ("Tecnólogo em Gestão de Recursos Humanos - 2º semestre","gestao de recursos humanos","Estágio em Recursos Humanos"),
            ("Graduação em Pedagogia","pedagogia","Estágio em Pedagogia"),
            ("Curso superior em Design","design","Estágio em Design"),
            ("Graduação em Engenharia Ambiental","engenharia ambiental","Estágio em Engenharia Ambiental"),
            ("Curso técnico em Segurança do Trabalho","seguranca do trabalho","Estágio Técnico em Segurança do Trabalho"),
        ]
        for resume,expected_course,compatible_title in cases:
            with self.subTest(resume=resume):
                profile=app.default_profile();profile["buscar_estagios"]=True
                app.adapt_profile_to_cv(profile,resume)
                courses=[app.norm(course) for course in profile["cursos_curriculo_detectados"]]
                self.assertIn(expected_course,courses)
                queries=[app.norm(query) for query in profile["consultas_gupy"]]
                self.assertIn("estagio "+expected_course,queries)
                self.assertEqual("OK_PERFIL",app.internship_course_status(
                    {"titulo":compatible_title,"descricao":""},profile))
                incompatible="Estágio em Marketing" if expected_course=="administracao" else "Estágio em Administração"
                self.assertEqual("FORA",app.internship_course_status(
                    {"titulo":incompatible,"descricao":""},profile))

    def test_compound_course_requires_more_than_one_generic_token(self):
        profile={"cursos_curriculo_detectados":["engenharia civil"]}
        self.assertEqual("FORA",app.internship_course_status(
            {"titulo":"Estágio em Engenharia Mecânica","descricao":""},profile))

    def test_explicit_safety_course_beats_generic_ads_words_in_company_description(self):
        profile={"cursos_curriculo_detectados":["direito","analise e desenvolvimento de sistemas"]}
        job={
            "titulo":"Estágio Técnico em Segurança do Trabalho",
            "descricao":("A organização trabalha com análise estratégica, tecnologia e inovação. "
                         "Promovemos o desenvolvimento do Estado e soluções para a indústria."),
        }
        self.assertEqual("FORA",app.internship_course_status(job,profile))

    def test_legal_profile_prioritizes_specific_titles_and_keeps_broad_terms(self):
        profile=app.default_profile();profile["buscar_estagios"]=True
        resume="Cursando Direito. Experiência profissional em rotinas jurídicas e contratos."
        app.adapt_profile_to_cv(profile,resume)
        queries=[app.norm(query) for query in profile["consultas_gupy"]]
        for expected in ("juridico","contratos","cobranca","estagio"):
            self.assertIn(expected,queries)
        self.assertIn("legal operations",queries)
        self.assertLess(queries.index("assistente juridico"),queries.index("juridico"))

    def test_v25_description_migration_is_additive_and_idempotent(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(titulo,url,fonte,descricao,status) VALUES('Pendente','https://vaga/1','LinkedIn','','Candidatado')")
        conn.execute("INSERT INTO vagas(titulo,url,fonte,descricao) VALUES('Completa','https://vaga/2','Gupy',?)",("Descrição completa "*20,))
        app.App.migrate_v25(instance);app.App.migrate_v25(instance)
        rows=conn.execute("SELECT titulo,status,description_status FROM vagas ORDER BY id").fetchall()
        self.assertEqual(("Pendente","Candidatado","pendente"),rows[0])
        self.assertEqual("disponivel",rows[1][2])
        self.assertEqual(2,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_v24_migration_backfills_without_changing_user_data(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE vagas(id INTEGER PRIMARY KEY, titulo TEXT, empresa TEXT, local TEXT, modalidade TEXT, descricao TEXT, url TEXT UNIQUE, fonte TEXT, data_publicacao TEXT, salario TEXT, score INTEGER, classificacao TEXT, motivo TEXT, status TEXT DEFAULT 'Nova', criada_em TEXT DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO vagas(titulo,empresa,local,modalidade,url,status) VALUES(?,?,?,?,?,?)",
                     ("Vaga preservada","Empresa preservada","Vitória, ES","Presencial — confirmado","https://vaga-antiga","Candidatado"))
        conn.execute("CREATE TABLE descartadas(id INTEGER PRIMARY KEY, titulo TEXT, empresa TEXT, local TEXT, descricao TEXT, url TEXT UNIQUE, fonte TEXT, data_publicacao TEXT, salario TEXT, motivo_descarte TEXT, descartada_em TEXT DEFAULT CURRENT_TIMESTAMP, workplace_type TEXT DEFAULT '', applicant_location_requirements TEXT DEFAULT '', structured_location_json TEXT DEFAULT '')")
        instance = object.__new__(app.App);instance.conn = conn;instance.p = self.profile
        app.App.db(instance)
        conn.execute("UPDATE vagas SET workplace_type='onsite',selecionada_lote=1 WHERE id=1")
        app.App.migrate_v24(instance)
        app.App.migrate_v24(instance)  # idempotência
        row=conn.execute("""SELECT titulo,empresa,status,selecionada_lote,workplace_type_raw,
                            workplace_source,structured_location_json,modality_checked_at FROM vagas""").fetchone()
        self.assertEqual(("Vaga preservada","Empresa preservada","Candidatado",1,"onsite","legacy"),row[:6])
        self.assertEqual("Vitória, ES",json.loads(row[6])["display"])
        self.assertTrue(row[7])
        self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_v24_migration_survives_close_and_reopen_of_legacy_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,"vagas_legado.db")
            conn=sqlite3.connect(path)
            conn.execute("CREATE TABLE vagas(id INTEGER PRIMARY KEY, titulo TEXT, empresa TEXT, local TEXT, modalidade TEXT, descricao TEXT, url TEXT UNIQUE, fonte TEXT, data_publicacao TEXT, salario TEXT, score INTEGER, classificacao TEXT, motivo TEXT, status TEXT DEFAULT 'Nova', criada_em TEXT DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("CREATE TABLE descartadas(id INTEGER PRIMARY KEY, titulo TEXT, empresa TEXT, local TEXT, descricao TEXT, url TEXT UNIQUE, fonte TEXT, data_publicacao TEXT, salario TEXT, motivo_descarte TEXT, descartada_em TEXT DEFAULT CURRENT_TIMESTAMP, workplace_type TEXT DEFAULT '', applicant_location_requirements TEXT DEFAULT '', structured_location_json TEXT DEFAULT '')")
            conn.execute("INSERT INTO vagas(titulo,empresa,local,modalidade,url,status) VALUES('Legada','Empresa','Brazil','Remoto Brasil — confirmado','https://legada','Entrevista')")
            conn.commit();conn.close()

            conn=sqlite3.connect(path)
            instance=object.__new__(app.App);instance.conn=conn;instance.p=self.profile
            app.App.db(instance);app.App.migrate_v24(instance);conn.close()

            conn=sqlite3.connect(path)
            row=conn.execute("SELECT titulo,status,remote_eligible_brazil,structured_location_json FROM vagas").fetchone()
            marker=conn.execute("SELECT valor FROM app_meta WHERE chave='migracao_v24_dados_estruturados'").fetchone()
            self.assertEqual(("Legada","Entrevista",1),row[:3])
            self.assertEqual("Brazil",json.loads(row[3])["display"])
            self.assertEqual(("1",),marker)
            conn.close()

    def test_modality_migration_reclassifies_old_remote_hint_without_deleting(self):
        conn = sqlite3.connect(":memory:")
        instance = object.__new__(app.App);instance.conn = conn;instance.p = self.profile
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(titulo,empresa,local,modalidade,descricao,url,fonte,workplace_type,status) VALUES(?,?,?,?,?,?,?,?,?)",
                     ("Vaga","Empresa","Brazil","Remoto Brasil — confirmado","","https://vaga","LinkedIn","","Nova"))
        app.App.migrate_v23(instance)
        row=conn.execute("SELECT modalidade,decisao FROM vagas").fetchone()
        self.assertEqual(("Verificar modelo","REVISAR"),row)
        self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_search_pipeline_saves_structured_location(self):
        instance = object.__new__(app.App)
        instance.conn = sqlite3.connect(":memory:", check_same_thread=False)
        app.App.db(instance)
        instance.p = self.profile
        instance.cv = "Experiência administrativa e atendimento"
        instance.collect = lambda _src: [{
            "titulo": "Assistente Administrativo",
            "empresa": "Empresa A",
            "local": "Vitória, ES",
            "descricao": "Rotinas administrativas e atendimento ao cliente.",
            "url": "https://example.test/vaga/1",
            "fonte": "Gupy",
            "source_brazil": True,
            "workplace_type": "onsite",
            "workplace_type_raw": "ON_SITE",
            "workplace_source": "structured",
            "structured_location": {"city":"Vitória","state":"ES","country":"BR"},
            "applicant_location_requirements": {"country":"BR"},
        }]
        instance.after = lambda _delay, callback: callback()
        instance.finish = lambda *_args: None
        instance.fail = lambda error: self.fail(error)
        with patch("app.load_profile",return_value=dict(self.profile)):
            app.App.run_source(instance, "gupy")
        row = instance.conn.execute("""SELECT workplace_type,location_confidence,location_evidence,
            workplace_type_raw,workplace_source,structured_location_json,
            applicant_location_requirements,remote_eligible_brazil,modality_checked_at FROM vagas""").fetchone()
        self.assertEqual(("onsite", "Alta", "workplace_type", "ON_SITE", "structured"), row[:5])
        self.assertEqual("Vitória",json.loads(row[5])["city"])
        self.assertEqual("BR",json.loads(row[6])["country"])
        self.assertIsNone(row[7])
        self.assertTrue(row[8])
        instance.conn.close()

    def test_main_filters_select_expected_modalities(self):
        conn = sqlite3.connect(":memory:")
        instance = object.__new__(app.App);instance.conn = conn
        app.App.db(instance)
        rows = [
            ("Remota", "Remoto Brasil — confirmado", "Geral"),
            ("Incerta", "Local/modalidade não confirmados", "Geral"),
            ("Presencial", "Presencial — confirmado", "Geral"),
            ("Estágio", "Híbrido — confirmado", "Estágio TI"),
            ("Auxiliar (PCD)", "Presencial — confirmado", "Geral"),
        ]
        for index,(title,mode,category) in enumerate(rows):
            conn.execute("INSERT INTO vagas(titulo,empresa,local,modalidade,descricao,url,score,categoria,decisao,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (title,"Empresa","Vitória",mode,"Descrição",f"https://vaga/{index}",80,category,"APROVADA","Nova"))
        def titles(view):
            sql,params=app.jobs_query(view,"")
            return {row[2] for row in conn.execute(sql,params)}
        self.assertEqual({"Remota"},titles("home_office"))
        self.assertEqual({"Remota"},titles("remoto"))
        self.assertEqual({"Presencial","Auxiliar (PCD)"},titles("presencial"))
        self.assertEqual({"Estágio"},titles("estagio"))
        self.assertEqual({"Auxiliar (PCD)"},titles("pcd"))
        self.assertEqual(5,len(titles("todas")))
        conn.close()

    def test_batch_selection_replaces_queue_without_deleting_jobs(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(1,'Uma','https://vaga/1','Nova',0)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(2,'Duas','https://vaga/2','Nova',1)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(3,'Três','https://vaga/3','Candidatado',1)")
        instance.batch_selection={1,3}
        class Info:
            value=""
            def set(self,value):self.value=value
        instance.info=Info();instance.refresh=lambda:None
        app.App.apply_batch_selection(instance)
        self.assertEqual([(1,)],conn.execute("SELECT id FROM vagas WHERE selecionada_lote=1").fetchall())
        self.assertEqual(3,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        self.assertEqual("Fila atualizada: 1 vaga(s).",instance.info.value)
        conn.close()

    def test_clear_queue_preserves_jobs(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(1,'Uma','https://vaga/1','Nova',1)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(2,'Duas','https://vaga/2','Nova',1)")
        instance.batch_selection={1,2};instance.refresh=lambda:None
        class Info:
            value=""
            def set(self,value):self.value=value
        instance.info=Info()
        removed=app.App.clear_batch(instance,ask=False)
        self.assertEqual(2,removed)
        self.assertEqual(0,conn.execute("SELECT COUNT(*) FROM vagas WHERE selecionada_lote=1").fetchone()[0])
        self.assertEqual(2,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_remove_single_job_from_queue_preserves_vacancy(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(1,'Uma','https://vaga/1','Nova',1)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(2,'Duas','https://vaga/2','Nova',1)")
        instance.batch_selection={1,2};instance.refresh=lambda:None
        class Info:
            value=""
            def set(self,value):self.value=value
        instance.info=Info()
        app.App.remove_from_batch(instance,1)
        self.assertEqual([(2,)],conn.execute("SELECT id FROM vagas WHERE selecionada_lote=1").fetchall())
        self.assertEqual(2,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        self.assertIn("continua na lista",instance.info.value)
        conn.close()

    def test_queued_job_hides_from_main_list_and_returns_when_removed(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("""INSERT INTO vagas(id,titulo,url,status,decisao,selecionada_lote)
                        VALUES(1,'Na fila','https://vaga/1','Nova','APROVADA',1)""")
        conn.execute("""INSERT INTO vagas(id,titulo,url,status,decisao,selecionada_lote)
                        VALUES(2,'Na lista','https://vaga/2','Nova','APROVADA',0)""")
        sql,params=app.jobs_query("todas","")
        self.assertEqual(["Na lista"],[row[2] for row in conn.execute(sql,params)])
        instance.batch_selection={1};instance.refresh=lambda:None
        class Info:
            def set(self,_value):pass
        instance.info=Info();app.App.remove_from_batch(instance,1)
        self.assertEqual({"Na fila","Na lista"},{row[2] for row in conn.execute(sql,params)})
        conn.close()

    def test_clear_search_archives_visible_jobs_and_preserves_queue_and_applications(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(1,'Visível','https://vaga/1','Nova',0)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(2,'Fila','https://vaga/2','Nova',1)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(3,'Histórico','https://vaga/3','Candidatado',0)")
        class Var:
            def set(self,_value):pass
        class Box:
            def configure(self,**_kwargs):pass
            def delete(self,*_args):pass
        instance.current=1;instance.q=Var();instance.view_mode=Var();instance.tv=Var();instance.meta=Var()
        instance.data_quality=Var();instance.info=Var();instance.desc_box=Box();instance.req_box=Box();instance.pay_box=Box()
        instance.refresh=lambda:None
        with patch.object(app.messagebox,"askyesno",return_value=True):
            self.assertEqual(1,app.App.clear_search(instance))
        rows=conn.execute("SELECT id,status,selecionada_lote FROM vagas ORDER BY id").fetchall()
        self.assertEqual((1,"Pesquisa limpa",0),rows[0])
        self.assertEqual((2,"Nova",1),rows[1])
        self.assertEqual((3,"Candidatado",0),rows[2])
        self.assertEqual(3,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_new_search_reactivates_saved_jobs_except_discarded_or_applications(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(1,'Anterior','https://vaga/1','Pesquisa limpa',0)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(2,'Arquivada','https://vaga/2','Arquivada',0)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(3,'Descartada','https://vaga/3','Ignorada',0)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(4,'Fila','https://vaga/4','Nova',1)")
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(5,'Candidatura','https://vaga/5','Candidatado',0)")
        instance.refresh=lambda:None
        self.assertEqual(2,app.App.reactivate_searchable_jobs(instance))
        rows=conn.execute("SELECT id,status,selecionada_lote FROM vagas ORDER BY id").fetchall()
        self.assertEqual([(1,"Nova",0),(2,"Nova",0),(3,"Ignorada",0),(4,"Nova",1),(5,"Candidatado",0)],rows)
        conn.close()

    def test_completed_application_leaves_queue_but_stays_in_history(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status,selecionada_lote) VALUES(1,'Uma','https://vaga/1','Nova',1)")
        app.App.mark_application_completed(instance,1)
        row=conn.execute("SELECT status,selecionada_lote,ultimo_resultado,candidatura_em FROM vagas WHERE id=1").fetchone()
        self.assertEqual(("Candidatado",0,"Candidatura confirmada pelo usuário"),row[:3])
        self.assertTrue(row[3])
        self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_v26_backfills_application_date_without_deleting_history(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(titulo,url,status,criada_em) VALUES('Antiga','https://vaga/antiga','Candidatado','2025-06-01 12:00:00')")
        app.App.migrate_v26(instance);app.App.migrate_v26(instance)
        row=conn.execute("SELECT titulo,status,candidatura_em FROM vagas").fetchone()
        self.assertEqual(("Antiga","Candidatado","2025-06-01 12:00:00"),row)
        self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_application_is_archived_not_deleted_from_summary(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("INSERT INTO vagas(id,titulo,url,status) VALUES(1,'Uma','https://vaga/1','Candidatado')")
        instance.refresh=lambda:None
        app.App.archive_application(instance,1)
        self.assertEqual(("Arquivada",),conn.execute("SELECT status FROM vagas WHERE id=1").fetchone())
        self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_manual_discard_can_be_restored_without_losing_vacancy(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn
        app.App.db(instance)
        conn.execute("""INSERT INTO vagas(id,titulo,empresa,local,descricao,url,fonte,status,selecionada_lote)
                        VALUES(1,'Uma','Empresa','Vitória, ES','Descrição','https://vaga/1','Gupy','Nova',1)""")
        instance.current=1;instance.batch_selection={1};instance.refresh=lambda:None
        class Info:
            def set(self,_value):pass
        instance.info=Info();instance.update_queue_action=lambda:None
        with patch.object(app.messagebox,"askyesno",return_value=True):
            app.App.discard_current(instance)
        self.assertEqual(("Ignorada",0),conn.execute("SELECT status,selecionada_lote FROM vagas WHERE id=1").fetchone())
        did=conn.execute("SELECT id FROM descartadas WHERE url='https://vaga/1'").fetchone()[0]
        self.assertTrue(app.App.restore_discarded_record(instance,did))
        self.assertEqual(("Nova",),conn.execute("SELECT status FROM vagas WHERE id=1").fetchone())
        self.assertEqual(0,conn.execute("SELECT COUNT(*) FROM descartadas").fetchone()[0])
        self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_http_session_is_reused_in_same_worker_thread(self):
        local=threading.local()
        with patch.object(app,"_HTTP_LOCAL",local),patch.object(app.requests,"Session",wraps=app.requests.Session) as factory:
            first=app.session();second=app.session()
        self.assertIs(first,second)
        self.assertEqual(1,factory.call_count)
        first.close()

    def test_detail_cache_waits_for_batch_before_writing(self):
        old_dirty=app.DETAIL_CACHE_DIRTY;old_last=app.DETAIL_CACHE_LAST_SAVE
        try:
            app.DETAIL_CACHE_DIRTY=1;app.DETAIL_CACHE_LAST_SAVE=app.time.time()
            with patch.object(app,"save_json_file") as save:
                self.assertFalse(app.flush_detail_cache())
                save.assert_not_called()
        finally:
            app.DETAIL_CACHE_DIRTY=old_dirty;app.DETAIL_CACHE_LAST_SAVE=old_last

    def test_detail_cache_force_flush_persists_pending_data(self):
        old_dirty=app.DETAIL_CACHE_DIRTY;old_last=app.DETAIL_CACHE_LAST_SAVE
        try:
            app.DETAIL_CACHE_DIRTY=1;app.DETAIL_CACHE_LAST_SAVE=app.time.time()
            with patch.object(app,"save_json_file") as save:
                self.assertTrue(app.flush_detail_cache(force=True))
                save.assert_called_once()
            self.assertEqual(0,app.DETAIL_CACHE_DIRTY)
        finally:
            app.DETAIL_CACHE_DIRTY=old_dirty;app.DETAIL_CACHE_LAST_SAVE=old_last

    def test_english_resume_builds_bilingual_profile_and_queries(self):
        resume="""Professional Summary
        Administrative Assistant with experience in customer service, contract management,
        Microsoft Excel, Microsoft Office and deadline management.
        Education
        Bachelor's degree in Law.
        Skills and responsibilities include filing and legal documents.
        """
        profile=app.default_profile()
        summary=app.adapt_profile_to_cv(profile,resume)
        self.assertEqual("Inglês",profile["idioma_curriculo_detectado"])
        self.assertIn("Administrativo",summary["areas"])
        self.assertIn("Atendimento",summary["areas"])
        self.assertIn("Jurídico",summary["areas"])
        self.assertIn("Excel",summary["skills"])
        self.assertTrue(any("direito" in course for course in summary["courses"]))
        self.assertIn("administrative assistant",profile["consultas_gupy"])
        self.assertIn("legal assistant",profile["consultas_linkedin"])
        self.assertTrue(any("jobs Brazil" in query for query in profile["consultas_google"]))
        self.assertTrue(any("vagas Brasil" in query for query in profile["consultas_google"]))

    def test_bilingual_queries_cover_roles_without_exceeding_existing_limits(self):
        resume="""Administrative Assistant and Legal Assistant with customer support,
        contract management, Microsoft Office and IT support experience."""
        profile=app.default_profile()
        profile["nivel_ingles"]="Fluente";profile["nivel_ingles_manual"]=True
        profile["buscar_vagas_internacionais"]=True
        profile["preferencia_internacional_manual"]=True
        app.adapt_profile_to_cv(profile,resume)
        expected={"administrative assistant","legal assistant","customer support","it support"}
        found={query.lower() for query in profile["consultas_gupy"]}
        self.assertTrue(expected.issubset(found))
        self.assertLessEqual(len(profile["consultas_gupy"]),40)
        self.assertLessEqual(len(profile["consultas_linkedin"]),35)
        self.assertLessEqual(len(profile["consultas_google"]),12)

    def test_disabled_internships_remove_portuguese_and_english_queries(self):
        resume="""Law student seeking an internship as legal intern.
        Professional skills include legal documents and Microsoft Office."""
        profile=app.default_profile();profile["buscar_estagios"]=False
        app.adapt_profile_to_cv(profile,resume)
        all_queries=profile["consultas_gupy"]+profile["consultas_linkedin"]+profile["consultas_google"]
        self.assertFalse(any("estagio" in app.semantic_norm(query) or "estagiario" in app.semantic_norm(query)
                             for query in all_queries))

    def test_english_resume_matches_portuguese_vacancy(self):
        resume="""Administrative Assistant with customer service, Microsoft Excel,
        Microsoft Office, contract management and filing experience.
        Professional experience supporting clients and managing legal documents."""
        profile=app.default_profile();app.adapt_profile_to_cv(profile,resume)
        vacancy={"titulo":"Assistente Administrativo","empresa":"Empresa",
                 "descricao":"Atendimento ao cliente, Excel, Pacote Office, contratos e documentação.",
                 "local":"Vitória, ES","workplace_type":"onsite"}
        score=app.score_job(vacancy,profile,resume)[0]
        self.assertGreaterEqual(score,70)

    def test_portuguese_profile_matches_english_vacancy(self):
        resume="""Assistente administrativo com atendimento ao cliente, Excel,
        Pacote Office, gestão de contratos e documentação."""
        profile=app.default_profile();app.adapt_profile_to_cv(profile,resume)
        vacancy={"titulo":"Administrative Assistant","empresa":"Company",
                 "descricao":"Customer service, Microsoft Excel, contract management and filing.",
                 "local":"Remote","workplace_type":"remote","source_brazil":True}
        score=app.score_job(vacancy,profile,resume)[0]
        self.assertGreaterEqual(score,70)

    def test_parallel_enrichment_preserves_order_and_failed_items(self):
        jobs=[
            {"titulo":"Primeira","empresa":"Empresa","local":"Brasil","descricao":"","url":"https://vaga/1","fonte":"Gupy"},
            {"titulo":"Segunda","empresa":"Empresa","local":"Brasil","descricao":"","url":"https://vaga/2","fonte":"Gupy"},
            {"titulo":"Terceira","empresa":"Empresa","local":"Brasil","descricao":"","url":"https://vaga/3","fonte":"Gupy"},
        ]
        def detail(url,_source):
            if url.endswith("/2"):raise RuntimeError("indisponível")
            return {"titulo":"","empresa":"","local":"","descricao":"Detalhes "+url,
                    "url":url,"fonte":"Gupy","workplace_type":"remote"}
        with patch.object(app,"generic_job_from_url",side_effect=detail):
            result=app.enrich_jobs_parallel(jobs,{"enriquecer_somente_se_necessario":True},"Gupy",max_workers=3)
        self.assertEqual(["Primeira","Segunda","Terceira"],[job["titulo"] for job in result])
        self.assertIn("/1",result[0]["descricao"])
        self.assertEqual("",result[1]["descricao"])
        self.assertIn("/3",result[2]["descricao"])

    def test_google_parallel_details_keep_discovery_order(self):
        urls=["https://vaga/1","https://vaga/2","https://vaga/3"]
        def detail(url,_source):
            return {"titulo":url.rsplit("/",1)[-1],"empresa":"Empresa","local":"Brasil",
                    "descricao":"Descrição completa "+("x"*140),"url":url,"fonte":"Google"}
        with patch.object(app,"google_urls",return_value=urls),patch.object(app,"generic_job_from_url",side_effect=detail):
            result=app.fetch_google({"consultas_google":["consulta"],"idade_maxima_vaga_dias":60})
        self.assertEqual(["1","2","3"],[job["titulo"] for job in result])

    def test_pcd_vacancy_obeys_visible_preference(self):
        vacancy={"titulo":"Assistente Administrativo (PCD)","descricao":"Atividades administrativas.",
                 "local":"Vitória, ES","data_publicacao":""}
        disabled=dict(self.profile,buscar_vagas_pcd=False)
        enabled=dict(self.profile,buscar_vagas_pcd=True)
        self.assertEqual((False,"vaga direcionada/exclusiva para PCD"),app.hard_filter(vacancy,disabled))
        self.assertTrue(app.hard_filter(vacancy,enabled)[0])

    def test_explicit_pcd_acceptance_is_recognized(self):
        vacancy={"titulo":"Assistente Administrativo",
                 "descricao":"Valorizamos a diversidade e incentivamos a candidatura de pessoas com deficiência.",
                 "local":"Vitória, ES","data_publicacao":""}
        self.assertEqual("vaga aberta para PCD",app.pcd_job_reason(vacancy))
        self.assertFalse(app.hard_filter(vacancy,dict(self.profile,buscar_vagas_pcd=False))[0])
        self.assertTrue(app.hard_filter(vacancy,dict(self.profile,buscar_vagas_pcd=True))[0])

    def test_generic_diversity_without_pcd_reference_is_not_filtered(self):
        vacancy={"titulo":"Assistente Administrativo",
                 "descricao":"Valorizamos a diversidade, a inclusão e diferentes histórias.",
                 "local":"Vitória, ES","data_publicacao":""}
        self.assertEqual("",app.pcd_job_reason(vacancy))
        self.assertTrue(app.hard_filter(vacancy,dict(self.profile,buscar_vagas_pcd=False))[0])

    def test_pcd_preference_moves_and_restores_without_deleting(self):
        conn=sqlite3.connect(":memory:")
        instance=object.__new__(app.App);instance.conn=conn;instance.refresh=lambda:None
        app.App.db(instance)
        conn.execute("""INSERT INTO vagas(id,titulo,empresa,local,descricao,url,fonte,status,selecionada_lote)
                        VALUES(1,'Auxiliar (PCD)','Empresa','Vitória, ES','Descrição','https://vaga/pcd','Gupy','Nova',0)""")
        self.assertEqual(1,app.App.apply_pcd_preference(instance,False))
        self.assertEqual(("Ignorada",),conn.execute("SELECT status FROM vagas WHERE id=1").fetchone())
        self.assertEqual(1,app.App.apply_pcd_preference(instance,True))
        self.assertEqual(("Nova",),conn.execute("SELECT status FROM vagas WHERE id=1").fetchone())
        self.assertEqual(0,conn.execute("SELECT COUNT(*) FROM descartadas").fetchone()[0])
        self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0])
        conn.close()

    def test_english_level_is_detected_independently_from_resume_language(self):
        resume="""Experiência profissional em atendimento e rotinas administrativas.
        Formação superior em andamento. Idiomas: Inglês - Intermediário (leitura e escrita)."""
        profile=app.default_profile();app.adapt_profile_to_cv(profile,resume)
        self.assertEqual("Português",profile["idioma_curriculo_detectado"])
        self.assertEqual("Intermediário",profile["nivel_ingles"])
        self.assertFalse(profile["buscar_vagas_internacionais"])

    def test_manual_english_level_and_international_choice_survive_resume_reload(self):
        profile=app.default_profile();profile.update({
            "nivel_ingles":"Básico","nivel_ingles_manual":True,
            "buscar_vagas_internacionais":False,"preferencia_internacional_manual":True,
        })
        app.adapt_profile_to_cv(profile,"Professional experience and education with skills and responsibilities in customer service work.")
        self.assertEqual("Básico",profile["nivel_ingles"])
        self.assertFalse(profile["buscar_vagas_internacionais"])

    def test_non_fluent_profile_reserves_queries_for_portuguese_jobs(self):
        profile=app.default_profile();profile["preferencia_internacional_manual"]=True
        profile["buscar_vagas_internacionais"]=False
        app.adapt_profile_to_cv(profile,"Experiência profissional como assistente administrativo e atendimento ao cliente.")
        self.assertFalse(profile["buscar_vagas_internacionais"])
        self.assertEqual([],profile["consultas_ingles"])
        self.assertNotIn("administrative assistant",profile["consultas_gupy"])
        self.assertNotIn("customer support",profile["consultas_linkedin"])

    def test_fluent_profile_enables_english_queries_and_international_sources(self):
        profile=app.default_profile();profile.update({
            "nivel_ingles":"Fluente","nivel_ingles_manual":True,
            "buscar_vagas_internacionais":True,"preferencia_internacional_manual":True,
        })
        app.adapt_profile_to_cv(profile,"Experiência profissional como assistente administrativo e atendimento ao cliente.")
        self.assertTrue(app.international_search_enabled(profile))
        self.assertIn("administrative assistant",profile["consultas_gupy"])
        self.assertIn("customer support",profile["consultas_linkedin"])

    def test_strong_matching_title_with_missing_description_stays_for_review(self):
        profile=app.default_profile();profile.update({
            "consultas_gupy":["assistente jurídico","analista jurídico júnior","analista de contratos"],
            "consultas_linkedin":[],"areas_curriculo_detectadas":["Jurídico"],
            "cidades_presencial":["Vitória"],"estado_local":"ES",
        })
        for title in ("Assistente Jurídico","Analista Jurídico JR","Analista de Contratos"):
            job={"titulo":title,"empresa":"Empresa","local":"Vitória, ES",
                 "descricao":"","workplace_type":"onsite","source_brazil":True}
            score=app.score_job(job,profile,"")[0]
            self.assertGreaterEqual(score,55,title)
            self.assertEqual("REVISAR",app.decision_level(job,profile,"Presencial — confirmado"))

    def test_broad_discovery_does_not_approve_onsite_job_from_another_state(self):
        profile={"cidades_presencial":["Vitória"],"estado_local":"ES","aceitar_remoto":True,
                 "idade_maxima_vaga_dias":60}
        job={"titulo":"Assistente Administrativo","local":"São Paulo, SP","workplace_type":"onsite"}
        self.assertEqual((False,"Presencial fora da região"),app.hard_filter(job,profile))


if __name__ == "__main__":
    unittest.main()
