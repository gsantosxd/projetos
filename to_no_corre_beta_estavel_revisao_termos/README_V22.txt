TÔ NO CORRE — V22 (ESTABILIZAÇÃO)

Teste experimental de currículo em inglês:

- A versão unificada ativa automaticamente as fontes internacionais para currículos em inglês.
- Currículos em português usam somente consultas e fontes nacionais por padrão, evitando resultados internacionais sem relação com o perfil.
- A configuração "Buscar vagas internacionais" permite alterar manualmente essa escolha.
- "Usar para outra pessoa" limpa currículo, perfil, vagas, fila, candidaturas, descartes, preferências e cache após duas confirmações.
- Currículos somente com ensino médio e sem histórico profissional recebem uma sugestão de busca de início de carreira, sem ativá-la automaticamente.
- A opção "Buscar vagas sem experiência / primeiro emprego" amplia as consultas para comércio, atendimento, logística, produção, serviços e administrativo.
- "Buscar Jovem Aprendiz" é uma opção separada, pois normalmente possui limite etário próprio.
- Quando selecionado, o modo de entrada prioriza anúncios compatíveis com ensino médio e sem experiência exigida.
- Vagas de Jovem Aprendiz encontradas por outras consultas ficam fora da lista quando a opção está desativada; a separação é reversível.
- O modo de entrada usa limites maiores apenas para esse perfil e acrescenta buscas por "sem experiência", "não exige experiência" e "ensino médio completo".
- Cidades digitadas com ou sem acento usam a mesma chave de busca e de filtragem; a grafia original continua visível nas configurações.
- Quando há várias cidades permitidas, o LinkedIn descobre vagas pelo estado e o aplicativo aplica depois o filtro exato de cidades.
- No modo de primeiro emprego, as consultas do Google são distribuídas entre todas as cidades cadastradas, evitando concentrar resultados somente na primeira.

- Detecta currículos em português, inglês ou com conteúdo misto.
- Normaliza localmente cargos, competências, escolaridade e experiência PT/EN.
- Gera consultas profissionais nos dois idiomas conforme as áreas identificadas.
- Compara currículo e vaga por conceitos bilíngues, sem API de tradução.
- Equilibra consultas em português e inglês dentro dos limites já existentes,
  incluindo cargos equivalentes de Jurídico, Administrativo, Atendimento e TI.
- O Google recebe até 12 consultas balanceadas PT/EN em vez de usar apenas os
  primeiros termos em português; filtros, localização e ranking não foram ampliados.
- Usa armazenamento permanente em %LOCALAPPDATA%\ToNoCorre\Data.

Beta 1.1 de testes:

- Limpeza interna sem alteração de fontes, filtros ou ranking.
- Remove imports, funções e callbacks antigos sem referências.
- Retira o diagnóstico de fontes que não possuía mais acesso pela interface.
- Grava o cache de detalhes em lotes e força a persistência ao concluir a busca
  e ao fechar o aplicativo.

- A versão experimental em inglês acrescenta Jobicy às fontes existentes.
- A nova fonte usa um feed público sem chave e tem cache de uma hora para evitar consultas repetidas.
- Vagas remotas internacionais só entram na lista principal quando a localização publicada aceita Brasil, LATAM ou candidatos do mundo todo.
- Preserva o banco SQLite e adiciona campos de modalidade/localização por migration.
- Usa as cidades do perfil na pesquisa presencial do LinkedIn.
- Exige confirmação de disponibilidade para o Brasil em vagas remotas internacionais.
- Usa o último currículo carregado durante a candidatura.
- Impede duas buscas simultâneas.
- Registra falhas técnicas em to_no_corre.log e mostra mensagens simples na interface.
- Remove configurações antigas de salário mínimo.
- Corrige falsos positivos de senioridade e anos de experiência.
- Adiciona testes locais de regressão em tests/test_stabilization.py.

ETAPA 2 — INTERFACE
- Cabeçalho com identidade Tô no Corre e ações principais destacadas.
- Filtros simples em uma faixa lateral com resumo discreto.
- Lista de vagas mais espaçosa, com compatibilidade, vaga, empresa e local/modelo.
- Painel de detalhes organizado em descrição, requisitos, salário e benefícios.
- Paleta suave em cinza azulado, azul e verde, com vermelho reservado ao descarte.
- Barra de status inferior com retorno simples sobre a busca.

ETAPA 3 — MODALIDADE
- Filtro remoto e booleanos legados não são aceitos como prova de trabalho remoto.
- Remoto exige modalidade confirmada e disponibilidade para Brasil/LATAM/Worldwide/Anywhere.
- Presencial e Híbrido exigem evidência explícita e local compatível com o perfil.
- Modalidade ausente, contraditória ou com alcance remoto indefinido aparece como Verificar modelo.
- Migration segura reclassifica vagas antigas sem apagar vagas ou candidaturas.

ETAPA 4 — PERSISTÊNCIA E MIGRATION
- SQLite preserva modalidade bruta, origem da evidência e localização estruturada em JSON.
- Restrições geográficas da candidatura e elegibilidade remota para o Brasil ficam persistidas.
- Data da última verificação de modalidade fica registrada.
- Migration V24 é aditiva e idempotente: não recria tabelas, não remove linhas e não altera status.
- Bancos antigos recebem backfill conservador usando os dados que já possuíam.

AJUSTE DE FILA EM LOTE
- Lista de vagas possui coluna FILA com marcação individual.
- Botão Incluir na fila mostra a quantidade marcada e grava o lote de uma vez.
- Desmarcar e confirmar atualiza a fila sem excluir a vaga.
- Ações Ver vaga e Descartar foram movidas para o cabeçalho dos detalhes.
- Rodapé redundante do painel de detalhes foi removido.
- Janela da fila possui ação Limpar fila, que não exclui vagas.
- Ao confirmar Candidatado, a vaga sai automaticamente da fila e permanece no histórico.
- Fila, Minhas candidaturas, Configurações e Diagnóstico abrem em instância única.
- Minhas candidaturas possui layout próprio de resumo, sem coluna FILA ou seleção em lote.
- Fechar Minhas candidaturas retorna à lista de vagas já carregada, sem executar nova busca.
- Candidaturas podem ser removidas do resumo por arquivamento, sem apagar o registro.
- Fora do perfil permanece como o diretório geral das vagas filtradas.
- O Resumo possui também a aba Descartadas, exclusiva para vagas descartadas manualmente pelo usuário; elas podem ser consultadas e restauradas.
- Restaurar todas devolve todas as vagas do diretório aberto, independentemente dos filtros de texto ou compatibilidade exibidos.
- A deduplicação combina título e empresa entre fontes, preservando níveis diferentes como Júnior e Pleno.
- Publicações de até 14 dias recebem um bônus pequeno e explicável, sem eliminar vagas antigas por esse critério.
- Vagas só são tratadas como encerradas quando há frase explícita ou uma data-limite estruturada já vencida.
- Vagas presenciais ou híbridas fora das cidades permitidas ficam sempre em Fora do perfil; compatibilidade alta não as devolve à lista principal.
- Descartes manuais permanecem protegidos quando a mesma vaga reaparece em uma nova busca.
- A primeira execução sem perfil cria configurações neutras e solicita o currículo; nenhuma busca pessoal vem pré-configurada.
- Após a busca, a barra inferior mostra somente recomendadas, vagas para conferir e vagas enviadas para Fora do perfil naquela busca.
- Vagas com descrição ausente ou curta recebem o aviso discreto Descrição incompleta.
- Configurações mostra apenas currículo, cidades, trabalho remoto e Salvar; navegador, período e manutenção ficam recolhidos em Opções avançadas.
- Opções avançadas e Salvar permanecem visíveis lado a lado na base do menu simplificado.
- Presencial e híbrido exigem correspondência exata de cidade e UF; Vitória/ES não coincide com Vitória da Conquista/BA.
- Configurações permite ativar ou desativar Buscar estágios; quando desligado, estágios saem da lista principal sem afetar fila ou candidaturas.
- A preferência de estágios é reaplicada ao abrir o aplicativo, antes da busca e ao final da coleta, evitando resultados residuais de tarefas concorrentes.
- Os quatro indicadores do resumo são atalhos acessíveis para seus respectivos conteúdos.
- O campo de busca filtra enquanto a pessoa digita; apagar o texto restaura a lista.
- Cabeçalhos da lista ordenam por fila, compatibilidade, vaga, empresa e local/modelo.
- O pequeno botão Limpar do campo textual foi removido por redundância.
- Cada linha de Minhas candidaturas possui uma ação Remover visível.
- Durante a coleta, o botão muda para Buscando, um indicador gira no topo e a barra inferior permanece animada.

VERSÃO INICIAL GENÉRICA — PERFIL PELO CURRÍCULO
- Configurações > Carregar meu currículo aceita PDF, DOCX ou TXT.
- O aplicativo identifica áreas, competências, termos recorrentes e cursos sem presumir Direito ou ADS/TI.
- As consultas e o ranking passam a usar o perfil derivado do currículo carregado.
- Ao trocar o currículo, as vagas existentes são reavaliadas; fila, candidaturas e descartes são preservados.
- Estágios são comparados com os cursos identificados. Dados insuficientes ficam para revisão.
- A migration V25 adiciona o acompanhamento de descrições pendentes sem recriar tabelas ou apagar registros.
- Configurações > Atualizar descrições pendentes tenta recuperar descrições do LinkedIn em lotes controlados.
- Falhas guardam tentativas, último erro e próxima tentativa; informação ausente não vira certeza.
- "Verificar modelo" agora preserva a classificação conservadora e mostra o motivo específico da pendência nos detalhes.
- Minhas candidaturas foi simplificada para data, vaga, empresa e remover; status e resumo foram retirados da tela.
- A migration V26 grava a data real das novas candidaturas e preenche registros antigos com a data já disponível, sem excluir histórico.
- Os filtros visíveis da lista são Todas, Presencial, Remoto e Estágios; Todas continua sendo a visão geral.
- O campo textual Buscar foi removido do topo para simplificar a tela; a coleta continua em Buscar vagas.
- Os detalhes da vaga agora mostram a data de publicação em formato dia/mês/ano.
- Antes das migrations, o aplicativo cria um backup diário recuperável em backups/ sem apagar backups anteriores.
- Uma segunda instância é bloqueada para evitar duas janelas gravando no mesmo SQLite.
- Janelas secundárias são abertas centralizadas dentro da janela principal.
- Os detalhes mostram fonte, qualidade dos dados e aviso de descrição pendente.
- Configurações possui a ação Reavaliar vagas para reaplicar currículo e preferências.
- Inclusões na fila e descartes registram preferências por termos; o ajuste no score é limitado e aparece na explicação.
- Sem currículo, as configurações abrem automaticamente para orientar o primeiro uso.
- A fila permite remover uma vaga individualmente, tanto pela coluna Ação quanto pelo botão Remover selecionada, sem excluir a vaga.
- A confirmação de candidatura agora é modal, centralizada e trazida para frente.
- Mesmo que o preenchimento da página falhe depois de abri-la, o aplicativo solicita a confirmação antes de seguir para a próxima vaga.
- Após confirmar uma candidatura, a próxima vaga abre imediatamente em uma nova aba e ganha foco antes da aba concluída ser fechada.
- Ao escolher Ainda não, a aba atual permanece aberta e a próxima vaga é aberta separadamente.
- Vagas incluídas na fila ficam ocultas da lista principal; ao removê-las ou limpar a fila, voltam automaticamente.
- O popup de confirmação usa altura baseada no conteúdo, botões alinhados e não deixa área vazia inferior.
- Fora do perfil mostra a compatibilidade com o currículo e permite filtrar por Todas, 50%+, 70%+ ou 85%+.
- A compatibilidade não restaura nem reclassifica automaticamente a vaga; o motivo original do descarte permanece visível.
- O botão Limpar pesquisa arquiva somente as vagas visíveis da pesquisa atual, sem apagar registros.
- Fila, candidaturas e Fora do perfil são preservados; vagas reencontradas em nova coleta são reativadas sem duplicação.
- Perfil de currículo V3 extrai formações linha a linha, remove período/semestre, rejeita consultas malformadas e amplia cargos de entrada.
- Consultas boas anteriores são combinadas com as novas em Gupy e LinkedIn, em vez de serem substituídas.
- A descoberta inclui mais cargos de entrada derivados das áreas do currículo e consulta duas páginas do LinkedIn por termo/modalidade antes de limitar resultados.
- O LinkedIn recebe o nome completo do estado para evitar interpretar UF brasileira como país estrangeiro.
- Local externo sem remoto confirmado fica provisoriamente em Fora do perfil, em vez de poluir a lista principal como Verificar modelo.
- O build Windows usa PyInstaller onedir; dados pessoais da Beta 1.1 ficam em
  %LOCALAPPDATA%\ToNoCorre\Beta1_1, isolados de todas as versões de teste anteriores.
- A coleta reutiliza conexões HTTP por thread e consulta em paralelo apenas as
  páginas de detalhes independentes da Gupy e dos resultados via Google. As
  consultas, filtros, limites, ordenação final e regras de compatibilidade não mudaram.
- Configurações agora oferece "Buscar vagas para PCD". Desativada, vagas com
  direcionamento, aceitação ou exclusividade PCD explícitos ficam em Fora do perfil; ativada,
  elas voltam à pesquisa e seguem normalmente os demais filtros e o ranking.
- O menu Mostrar vagas inclui "Vagas PCD", reunindo anúncios direcionados,
  exclusivos ou que aceitam explicitamente candidaturas de pessoas com deficiência.
- A lista principal possui a coluna Publicação em DD/MM/AAAA, ordenável pelo cabeçalho, com indicação para datas não informadas.
- A busca completa consulta doze fontes em paralelo, em vez de aguardar cada fonte terminar para iniciar a próxima.
- Himalayas usa buscas em inglês derivadas do currículo, filtradas para Brasil e resultados Worldwide, com cache diário.
- Remote Landers consulta vagas remotas originadas diretamente em ATS e preserva a restrição geográfica publicada, com cache de dez minutos.
- Remote Game Jobs e Work With Indies são lidos pelos feeds RSS públicos, com cache de uma hora.
- Hitmarker e Vagas em Games entram por consultas restritas no Google, com volume reduzido para limitar o impacto no tempo de busca.
- Todas as novas fontes passam pelos mesmos filtros, ranking e deduplicação das vagas existentes.
- O LinkedIn entrega primeiro os cartões da busca; descrições pendentes são enriquecidas automaticamente em segundo plano em lotes controlados.

CURRÍCULO EM INGLÊS

- Configurações permite declarar o nível de inglês como Não informado, Básico,
  Intermediário ou Fluente; a escolha manual é preservada ao recarregar o currículo.
- Exigências explícitas de inglês básico, intermediário ou fluente são comparadas
  ao nível declarado antes de uma vaga ser recomendada.
- Títulos profissionais em inglês também entram nas consultas brasileiras, pois
  empresas nacionais podem publicar cargos em inglês sem que a vaga seja internacional.
- Um currículo identificado com alta confiança como predominantemente em inglês registra "Inglês fluente" entre as competências usadas no match.
- Currículos curtos, mistos ou indefinidos não recebem fluência automaticamente.
- Termos como "fluent English" e "advanced English" são normalizados para comparação com vagas em português e inglês.
- A Jobicy é consultada com até seis cargos em inglês derivados do currículo, em paralelo e com cache, em vez de usar somente o feed geral.
- Uma exigência de inglês fluente deixa de bloquear a vaga quando essa fluência foi identificada no currículo.
- A palavra genérica "process" não é mais interpretada isoladamente como experiência em processos jurídicos.

TEMA ESCURO E EXCLUSÃO DE LOCALIDADES

- A interface principal e as janelas secundárias usam uma paleta escura com alto contraste.
- Configurações permite informar localidades indesejadas separadas por vírgula, preferencialmente no formato Cidade/UF, estado ou país.
- A comparação considera somente a localização publicada e os requisitos estruturados da vaga.
- As vagas são preservadas no diretório acessível "Localidades excluídas" e voltam à pesquisa quando a regra correspondente é removida.
- Modalidade e localização estruturada continuam armazenadas durante exclusão e restauração.
- O cache de detalhes possui trava para gravações concorrentes e o ranking é recalculado quando novas descrições chegam.
- Compatibilidade e localização são tratadas separadamente: presencial ou híbrido fora da região fica em Fora do perfil, independentemente da compatibilidade.
- Fora do perfil permite consultar a compatibilidade e restaurar uma vaga específica ou todas as vagas do diretório.
- A interface não possui histórico manual de pesquisas: ao buscar novamente, vagas salvas em Pesquisa limpa ou Arquivada voltam automaticamente.
- Somente vagas explicitamente descartadas permanecem fora da lista; modalidade e localização continuam usando a auditoria conservadora atual.

COBERTURA LOCAL DA GUPY

- A coleta da Gupy consulta diretamente o estado escolhido pelo usuário. Isso evita que vagas locais de cargos muito comuns fiquem escondidas depois das primeiras páginas de resultados nacionais.
- Quando vagas remotas estão habilitadas, uma consulta nacional separada usa o filtro estruturado remoto da própria fonte.
- A validação local posterior continua ativa: a ampliação da coleta não libera vagas presenciais ou híbridas fora das cidades configuradas.

JOVEM APRENDIZ

- Quando habilitadas, as consultas específicas de Jovem Aprendiz são executadas antes dos cargos gerais para não serem ocultadas pelos limites das fontes.
- O menu Mostrar vagas possui o filtro Jovem Aprendiz, que exibe somente anúncios de aprendizagem sem apagar ou esconder permanentemente as demais vagas.
- As consultas são reconstruídas no início de cada pesquisa; mudanças nas opções passam a valer sem reenviar o currículo.

COBERTURA DE VAGAS JURÍDICAS

- Currículos da área jurídica usam também os termos amplos "jurídico", "contratos" e "cobrança", pois algumas fontes não encontram bem títulos compostos.
- Quando estágios estão habilitados, a descoberta inclui o termo amplo "estágio"; o filtro de curso continua impedindo que estágios incompatíveis sejam recomendados.
- Os termos amplos são consultados antes dos cargos específicos, mantendo depois as mesmas regras de localização, modalidade, PCD, formação e compatibilidade.
- A formação explicitada no título também é validada, inclusive em anúncios sem descrição completa e nas formas "estagiária" e "estagiário".
- A consulta nacional "legal operations", existente na versão Beta 1, permanece disponível para currículos jurídicos em português.
- Ao carregar o perfil ou iniciar uma busca, estágios já salvos também são reavaliados; os incompatíveis vão para Fora do perfil sem serem apagados.

FORMAÇÕES DIVERSAS

- A extração de formação aceita Graduação, Bacharelado, Tecnólogo, Curso superior, Curso técnico, Formação acadêmica e curso seguido de semestre ou "cursando".
- A validação automatizada inclui Administração, Ciências Contábeis, Psicologia, Enfermagem, Engenharia Civil, Marketing, Recursos Humanos, Pedagogia, Design, Engenharia Ambiental e Segurança do Trabalho.
- Sincronização de nomes permite, por exemplo, Ciências Contábeis/Contabilidade e Gestão de Recursos Humanos/Recursos Humanos.
- Cursos compostos exigem correspondência suficiente dos termos para não confundir Engenharia Civil com Engenharia Mecânica.
- A formação explícita no título da vaga tem prioridade sobre palavras genéricas da descrição institucional; por exemplo, "Segurança do Trabalho" não combina com ADS apenas porque o texto menciona análise e desenvolvimento.

PRIVACIDADE E SEGURANÇA — BETA 0.9.1

- A primeira abertura exige leitura do aviso de privacidade versionado; o texto também fica acessível em Configurações.
- A preferência por vagas PCD possui confirmação específica, registrada localmente e removida quando a opção é desativada.
- Limpar tudo também remove perfil do navegador, cookies, sessões, logs, backups e currículos legados, e usa exclusão segura do SQLite antes de compactá-lo.
- No executável Windows, a pasta de dados recebe permissões restritas ao usuário atual, SYSTEM e administradores.
- O executável mostra a versão 0.9.1-beta e recebe metadados formais de versão no build.
- Dependências de execução e empacotamento estão fixadas em versões testadas.
- O build usa `%LOCALAPPDATA%\ToNoCorre\Data` e importa uma única vez os dados da edição `Beta0_9_0`, sem apagar a cópia anterior.
- A distribuição inclui PRIVACIDADE.md, mas um canal de contato válido ainda deve ser informado antes da publicação aberta.
- O backup agora usa a API do SQLite e inclui dados confirmados ainda presentes no WAL.
- São mantidos no máximo sete backups e três arquivos de diagnóstico de até 1 MB.
- Perfil e cache são gravados de forma atômica para evitar arquivos incompletos após interrupções.
- Ao fechar durante uma tarefa, o aplicativo solicita cancelamento e aguarda os workers antes de fechar o banco.
- O iniciar.bat abre a interface por `pythonw`/`pyw`, sem manter um CMD vazio na tela.

BUSCA CUMULATIVA DIÁRIA

- Resultados recentes de cada fonte são mantidos em cache local separado por perfil
  de pesquisa, sem armazenar ou enviar o currículo completo nesse cache.
- Consultas repetidas usam um intervalo seguro: uma hora para a Gupy, seis horas
  para o LinkedIn e três horas para as demais fontes.
- Se uma fonte falhar ou devolver zero vagas durante uma limitação temporária, os
  resultados recentes válidos são reutilizados em vez de desaparecerem da lista.
- A cada nova coleta bem-sucedida, vagas novas e recentes são combinadas com as
  anteriores, deduplicadas e novamente submetidas aos filtros atuais.
- A Gupy preserva os primeiros resultados de cada cargo e alterna diariamente uma
  segunda parte da lista, aumentando a cobertura ao longo dos dias.
- O diagnóstico registra, por fonte, quantas vagas vieram da consulta atual, do
  cache ou de fallback após falha.
- "Limpar tudo / trocar currículo" também remove integralmente esse cache.
