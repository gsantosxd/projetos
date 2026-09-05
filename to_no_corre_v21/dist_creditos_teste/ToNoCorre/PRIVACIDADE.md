# Privacidade — Tô no Corre 0.9.3-beta-estável

O Tô no Corre processa o currículo localmente para pesquisar, organizar e comparar vagas. Ele não possui servidor próprio, telemetria ou venda de dados.

## Dados armazenados

O computador do usuário pode armazenar o currículo original e seu texto extraído, cursos e competências identificados, preferências de busca, cidades, vagas, fila, candidaturas, descartes, cache, diagnóstico, backups e um perfil separado do navegador usado nas candidaturas.

Esses arquivos ficam em `%LOCALAPPDATA%\ToNoCorre\BetaEstavel2` na edição empacotada. A pasta recebe permissões restritas à conta do Windows, ao sistema e aos administradores. Isso não impede acesso por alguém que controle a conta ou seja administrador do computador.

Ao atualizar a partir da edição beta 0.9.0, os dados existentes podem ser copiados uma única vez da pasta anterior. A pasta antiga não é apagada automaticamente, evitando perda de dados; o usuário pode removê-la depois de confirmar que a atualização foi concluída corretamente.

## Comunicações externas

Durante a busca, fontes de vagas recebem termos profissionais e localidades. O currículo completo não é enviado nessa etapa. Ao iniciar uma candidatura, o navegador acessa o site escolhido e pode preencher campos ou anexar o currículo para revisão. O aplicativo não confirma nem envia a candidatura automaticamente.

Cada site de vagas é um serviço independente e possui sua própria política de privacidade.

## Vagas para PCD

A preferência por vagas direcionadas ou abertas para PCD é opcional e pode permitir uma inferência relacionada à saúde. Sua ativação exige confirmação específica. A preferência pode ser desativada nas configurações ou removida com a limpeza completa.

## Retenção e exclusão

Os dados permanecem no computador até o usuário utilizar `Configurações > Limpar tudo / trocar currículo`. A limpeza remove currículo, banco, backups, cache, diagnóstico, cookies e sessões do navegador mantidos por esta edição. O aplicativo conserva no máximo sete backups automáticos do banco e três arquivos rotativos de diagnóstico de até 1 MB cada. A exclusão lógica não substitui recursos de apagamento seguro do próprio dispositivo, especialmente em SSDs e cópias externas.

## Direitos e contato

Como os dados do aplicativo ficam sob controle local, o usuário pode consultá-los e apagá-los no próprio programa. Antes da distribuição pública deverá ser informado aqui um canal válido para dúvidas, solicitações e incidentes.

**Canal de privacidade:** enquanto esta for uma versão de testes, utilize o mesmo canal pelo qual o aplicativo foi fornecido. Um contato permanente deverá constar aqui antes da distribuição pública aberta.
