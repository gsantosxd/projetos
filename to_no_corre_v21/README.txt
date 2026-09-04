ASSISTENTE DE CANDIDATURAS V9 — BUSCA POR FAMÍLIAS

A busca foi reorganizada em quatro famílias: Jurídico, Estágio Direito, Estágio ADS/TI e Geral.

O score não elimina mais vagas efetivas; apenas ordena. Estágios continuam restritos a Direito ou ADS/TI. A interface ganhou coluna/filtro Categoria. Os filtros objetivos de localização/modalidade, PCD exclusiva, vaga encerrada, idade e requisito impeditivo continuam ativos.

ASSISTENTE DE CANDIDATURAS V8.4 — MODALIDADE/LOCALIZAÇÃO MAIS PRECISAS

CORREÇÕES DO TESTE V8.3

1) GUPY
O tipo de ambiente de trabalho informado pela própria Gupy agora é preservado e tem prioridade:
remote / hybrid / onsite.

2) "HOME OFFICE" NÃO É MAIS PROVA FORTE SOZINHO
Uma ocorrência perdida de "home office" ou "remoto" no corpo do anúncio não transforma
automaticamente uma vaga de Manaus, Brasília, São Paulo etc. em vaga remota.
Para ignorar uma cidade explícita fora da região, agora é necessário:
- workplace type remoto da fonte; OU
- frase inequívoca como "100% remoto", "totalmente remoto", "fully remote",
  "modalidade remota", "modelo remoto", "work from anywhere"; OU
- remoto/home office declarado diretamente no título/local.

3) LOCALIZAÇÃO BRASILEIRA
Foram adicionadas todas as UFs e nomes de estados, inclusive Distrito Federal, Amazonas etc.

4) VAGAS.COM
O coletor não usa mais o texto inteiro do card como se fosse localização.
Ele abre a vaga e tenta obter local/título via JobPosting. Se não conseguir, marca local como
"Não informado" em vez de inventar uma cidade.

5) CIDADES FORA DA REGIÃO
Cidade/estado explícito fora das cidades permitidas + sem remoto confiável = DESCARTA.

A trilha jurídica privilegiada permanece ativa.

ASSISTENTE DE CANDIDATURAS V8.3 — LOCALIZAÇÃO CORRIGIDA

O teste da V8.2 mostrou que o filtro ficou permissivo demais para modalidade incerta.

REGRA NOVA:
- Remoto confirmado: entra, mesmo que a empresa/sede mencione outra cidade.
- Presencial/híbrido confirmado na região permitida: entra.
- Presencial/híbrido confirmado fora da região: descarta.
- Cidade/UF brasileira explícita fora da região + SEM evidência forte de remoto: descarta.
- Cidade da região permitida sem modalidade explícita: entra como modalidade incerta local.
- Só vira "Verificar modalidade/local" quando o anúncio realmente não permite determinar
  se é remoto ou onde o trabalho será realizado.

Exemplo:
"Vitória da Conquista, BA" sem "100% remoto" -> DESCARTA.
"São Paulo, SP" + "100% remoto" -> ENTRA.
"Vitória, ES" sem modalidade clara -> ENTRA.
"Brasil" sem modalidade clara -> VERIFICAR.

A trilha jurídica privilegiada e o filtro PCD estrito da V8.2 permanecem.

ASSISTENTE DE CANDIDATURAS V8.2 — FILTRO JURÍDICO E MODALIDADE REVISADOS

1. TRILHA JURÍDICA
Vagas com evidência jurídica não passam mais pelo filtro genérico de compatibilidade.
Também não são eliminadas por score baixo. Recebem bônus de análise e permanecem disponíveis.

2. MODALIDADE
- remoto confirmado tem prioridade sobre a cidade/sede informada;
- presencial/híbrido confirmado fora da região continua sendo descartado;
- presencial/híbrido na região permitida continua entrando;
- modalidade realmente incerta NÃO é descartada: aparece como "Verificar modalidade/local".

3. PCD
O detector ficou mais estrito. Só elimina quando há linguagem explícita de exclusividade,
reserva ou ação afirmativa PCD no cabeçalho/início do anúncio. Textos genéricos de diversidade
não eliminam mais a vaga.

4. RESUMO
Também foi corrigida a formatação do resumo de descartes.

TESTE
Faça BUSCAR TUDO. Depois abra "Resumo descartes".
Compare especialmente os números de:
- modalidade/localização fora dos critérios
- vaga não compatível
- exclusiva/afirmativa PCD
e confira as novas vagas marcadas "Verificar modalidade/local".

ASSISTENTE DE CANDIDATURAS V8.1 — AUDITORIA DE DESCARTES + PCD

NOVIDADES

1) Nenhum descarte fica mais invisível.
Toda vaga eliminada durante a busca é registrada na tabela de descartadas com:
- título
- empresa
- local
- fonte
- descrição
- link
- motivo exato do descarte

2) Botão "Ver descartadas"
Abre a lista completa das vagas eliminadas. É possível pesquisar, ler a descrição,
abrir o anúncio original e até restaurar manualmente uma vaga para a lista principal.

3) Botão "Resumo descartes"
Mostra quantas vagas caíram em cada regra. Exemplo:
- modalidade/localização fora dos critérios
- vaga não compatível
- score abaixo do mínimo
- vaga antiga
- ensino superior completo
- vaga encerrada
- estágio fora de Direito/ADS
- vaga exclusiva/afirmativa para PCD

4) Vagas exclusivas para PCD
Vagas claramente exclusivas, reservadas ou afirmativas para PCD são descartadas.
Anúncios inclusivos que apenas dizem que PCDs também são bem-vindos NÃO são descartados.

5) Revalidar tudo
Quando uma vaga da lista principal passa a ser descartada na revalidação,
ela é movida para o histórico de descartadas em vez de simplesmente desaparecer.

TESTE RECOMENDADO
Faça uma nova BUSCAR TUDO e depois clique em "Resumo descartes".
Esse resumo mostrará exatamente qual filtro está reduzindo demais o volume.

ASSISTENTE DE CANDIDATURAS V8 — PENTE-FINO DE CARGOS JURÍDICOS

A lista de busca/relevância jurídica foi ampliada para reconhecer famílias de cargos como:

- Assistente/Auxiliar/Analista Jurídico Júnior
- Assistente/Auxiliar Administrativo Jurídico
- Departamento Jurídico / Apoio Jurídico / Secretariado Jurídico
- Paralegal / Assistente Paralegal
- Controller Jurídico / Controladoria Jurídica
- Assistente/Auxiliar/Analista Júnior de Controladoria Jurídica
- Legal Operations / Legal Ops / Legal Assistant / Legal Support
- Backoffice Jurídico / Operações Jurídicas
- Assistente/Auxiliar Processual / Processos Jurídicos
- Prazos / Publicações / Protocolos / Diligências
- Correspondente Jurídico / Preposto Jurídico
- Contratos / Gestão de Contratos
- Compliance / Governança Jurídica / Regulatório
- Societário / Legalização
- Documentação e Cadastro Jurídico
- Atendimento/Relacionamento Jurídico
- Cobrança Jurídica / Recuperação de Crédito Jurídico
- Contencioso (cível, trabalhista, tributário etc.)

Também foram adicionados termos de atividade jurídica ao analisador:
PJe, Eproc, e-SAJ, Projudi, publicações, intimações, prazos processuais, protocolos,
andamento/acompanhamento processual, petições, recursos, diligências, guias,
sistemas jurídicos, gestão de processos e carteira processual.

IMPORTANTE:
A presença do nome do cargo aumenta a chance de a vaga ser coletada/analisada, mas os demais
filtros continuam valendo (localização/modalidade, vaga encerrada, idade, formação obrigatória etc.).

ASSISTENTE DE CANDIDATURAS V7.6 — SEM FILTRO DE SALÁRIO

Mudança:
- salário NÃO elimina mais nenhuma vaga;
- vagas abaixo de R$ 2.000 podem aparecer;
- estágios abaixo de R$ 1.400 também podem aparecer;
- salário não informado continua aparecendo;
- quando a remuneração é identificada, ela continua sendo exibida apenas como informação;
- salário não aumenta nem reduz o score de compatibilidade.

Os demais filtros permanecem:
- estágio somente Direito ou ADS/TI;
- modalidade/localização;
- vagas encerradas;
- idade da publicação;
- ensino superior completo obrigatório;
- compatibilidade com currículo;
- fila sequencial de candidaturas.

Ao abrir esta versão, use "Revalidar tudo" e depois "BUSCAR TUDO".

ASSISTENTE DE CANDIDATURAS V7.5 — BUSCA MAIS AMPLA + ESTÁGIOS RESTRITOS

MUDANÇAS PRINCIPAIS

1) ESTÁGIOS
Agora estágio só entra quando a vaga estiver claramente ligada a:
- Direito / Jurídico / Legal / Advocacia / Paralegal; OU
- Análise e Desenvolvimento de Sistemas / TI / Sistemas / Desenvolvimento de Sistemas /
  Desenvolvimento de Software / Suporte Técnico / Help Desk / Service Desk.

Estágios administrativos, RH, marketing, contabilidade etc. são descartados mesmo que o título
tenha palavras que combinam com outras experiências do currículo.

2) VAGAS NORMAIS
A busca ficou mais ampla. Não depende apenas de meia dúzia de cargos.
Procura oportunidades compatíveis nas famílias:
- administrativo e operações;
- atendimento, CX, SAC e ouvidoria;
- jurídico, contratos, paralegal e compliance;
- suporte N1, help desk e service desk;
- cadastro, documentação, faturamento e rotinas financeiras de entrada.

3) REMUNERAÇÃO
- Vaga normal com salário identificado abaixo de R$ 2.000: descartada.
- Vaga normal com salário identificado em R$ 2.000 ou mais: aceita se passar nos demais filtros.
- Salário não informado: continua sendo mantido, pois muitas empresas só revelam remuneração
  depois da triagem.
- Estágio mantém bolsa mínima de R$ 1.400.

4) IMPORTANTE
Clique em "Revalidar tudo" uma vez ao abrir esta versão para reaplicar as regras à lista existente.

ASSISTENTE DE CANDIDATURAS V7.4 — QUALIDADE + FILA SEQUENCIAL

CORREÇÕES DESTA VERSÃO

1) MODALIDADE MAIS CONSERVADORA
- Resultado encontrado por uma busca "remote" não é considerado remoto por si só.
- Cidade específica fora da Grande Vitória + ausência de "100% remoto"/modelo remoto = descartada.
- Presencial e híbrido continuam aceitos apenas em Cariacica, Vitória, Vila Velha e Viana.
- Termos genéricos como "home office" perderam força quando o anúncio aponta outra cidade.

2) VAGAS ENCERRADAS/FINALIZADAS
- Detecta textos como "vaga encerrada", "não aceita mais candidaturas",
  "inscrições encerradas", "job no longer available", "applications closed" etc.
- A checagem ocorre na coleta e novamente na página AO ABRIR A CANDIDATURA.
  Isso pega vagas que fecharam depois da busca.

3) ENSINO SUPERIOR COMPLETO
- Vagas que explicitamente exigem ensino superior/graduação completa são descartadas.
- Não descarta "cursando", "completo ou cursando", "em andamento" nem formação apenas desejável.

4) LOTE CORRIGIDO
- A versão anterior não esperava de verdade o fechamento da mensagem e ainda possuía espera de 30–90 s.
- Agora cada vaga abre, o programa prepara a candidatura e ESPERA sua decisão.
- Botões:
  "Candidatado → próxima" = marca como candidatado e abre a próxima.
  "Pular → próxima" = não marca e abre a próxima.
  "Parar lote" = encerra a sessão.
- Intervalo manual padrão entre uma vaga e outra: apenas 2 segundos.

ANTES DE USAR A FILA
Clique em "Revalidar tudo" uma vez. Ele reprocessa a lista antiga com todas essas regras.

ASSISTENTE DE CANDIDATURAS V7.3 — FILTRO DE TEMPO

Novo filtro:
- padrão: somente vagas publicadas nos últimos 60 dias;
- vagas com data identificável acima de 60 dias são descartadas;
- vagas sem data confiável são mantidas, para não perder oportunidade por falha da fonte;
- botão "Remover antigas" limpa vagas antigas que já estejam no banco.

Para mudar o limite, edite perfil.json:
"idade_maxima_vaga_dias": 60

Sugestões:
30 = agressivo, prioriza vagas muito novas
60 = padrão recomendado
90 = mais amplo

ASSISTENTE DE CANDIDATURAS V7.2 — VALIDAÇÃO DE MODALIDADE

Correção principal:
A busca por "remote" não é mais considerada prova de que a vaga é remota.

A V7.2 valida o texto real da vaga:
- presencial / on-site -> Presencial
- híbrido / hybrid -> Híbrido
- 100% remoto / home office / fully remote etc. -> Remoto confirmado
- sem evidência suficiente -> Modalidade incerta

Regras:
- Remoto confirmado e elegível no Brasil: aceita.
- Presencial/Híbrido: somente Cariacica, Vitória, Vila Velha e Viana.
- Modalidade incerta fora dessas cidades: descarta.
- Remoto internacional sem território compatível confirmado: descarta.

IMPORTANTE AO MIGRAR DA V7.1
Clique uma vez em "Revalidar modalidade".
Isso limpa/reclassifica as vagas que já estavam salvas com a lógica antiga.
Depois use BUSCAR TUDO normalmente.

ASSISTENTE DE CANDIDATURAS V7.1 — BRAVE

Mudança principal:
- A automação agora usa o Brave instalado no Windows.
- O programa tenta localizar brave.exe automaticamente.
- Não é necessário instalar o Chromium do Playwright.

PRIMEIRO USO
1. Extraia a pasta.
2. Execute preparar_brave.bat uma vez.
3. Execute iniciar.bat.
4. Faça BUSCAR TUDO.
5. Selecione as vagas com Selecionar 75%+.
6. Clique Iniciar lote.
7. Na primeira abertura do Brave automatizado, faça login nos sites necessários.
8. Esse login ficará salvo no perfil browser_profile_brave.

IMPORTANTE SOBRE SEUS DADOS DO BRAVE
A V7.1 usa o executável do Brave, mas NÃO aponta diretamente para o perfil pessoal já aberto no seu Brave.
Isso evita conflito de perfil, bloqueio de arquivos e risco de corrupção.
Você faz login uma vez no perfil browser_profile_brave e ele mantém cookies/sessões dali em diante.

Se o Brave não for encontrado:
Abra perfil.json e preencha:
"brave_executable_path": "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"

AUTOENVIO
Continua DESATIVADO por padrão:
"autoenviar_formularios_simples": false

O programa:
- preenche dados conhecidos;
- tenta anexar curriculo.pdf;
- mantém sessão do Brave;
- não contorna CAPTCHA;
- não responde perguntas desconhecidas inventando informação;
- deixa revisão manual como padrão.
