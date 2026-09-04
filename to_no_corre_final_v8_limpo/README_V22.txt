TÔ NO CORRE — V22 (ESTABILIZAÇÃO)

- Mantém as fontes existentes; nenhuma fonte nova foi adicionada.
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
- A lista principal possui a coluna Publicação em DD/MM/AAAA, ordenável pelo cabeçalho, com indicação para datas não informadas.
- A busca completa consulta cinco fontes em paralelo, em vez de aguardar cada fonte terminar para iniciar a próxima.
- O LinkedIn entrega primeiro os cartões da busca; descrições pendentes são enriquecidas automaticamente em segundo plano em lotes controlados.
- O cache de detalhes possui trava para gravações concorrentes e o ranking é recalculado quando novas descrições chegam.
- Compatibilidade e localização agora são tratadas separadamente: vagas 70%+ fora da região podem permanecer na lista como Revisar, sem serem chamadas de remotas.
- Configurações permite ativar/desativar esse comportamento, e Fora do perfil pode restaurar em lote todas as vagas exibidas pelo filtro atual.
- A interface não possui histórico manual de pesquisas: ao buscar novamente, vagas salvas em Pesquisa limpa ou Arquivada voltam automaticamente.
- Somente vagas explicitamente descartadas permanecem fora da lista; modalidade e localização continuam usando a auditoria conservadora atual.
