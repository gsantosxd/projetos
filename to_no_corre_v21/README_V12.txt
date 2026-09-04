V12 — LIMPEZA E PRECISÃO

Mudanças:
- Vagas.com.br removido da coleta e da interface.
- Dados estruturados primeiro; página completa só é aberta quando faltam informações úteis.
- Vagas antigas são descartadas o mais cedo possível quando a fonte informa uma data confiável.
- Deduplicação entre fontes e entre execuções usando título+empresa/local normalizados.
- A mesma vaga encontrada em várias fontes guarda a lista de fontes.
- Prioridade de fonte: Gupy > LinkedIn > Indeed/Google > Google > Remotive.
- Score explicável por componentes no campo "Análise".
- Motivo genérico final de localização foi substituído por motivo específico.
- Estágio fora da área tenta informar o curso detectado.
- Mantidos cache, Saúde das fontes, APROVADA / REVISAR / DESCARTADA e automação Brave.

TESTE
1. BUSCAR TUDO.
2. Abrir Saúde fontes.
3. Conferir APROVADA.
4. Conferir REVISAR.
5. Abrir Resumo dos descartes.
6. Selecionar algumas vagas e verificar o novo texto "Análise".
7. Se a mesma vaga aparecer em duas fontes, conferir "fontes:" no painel direito.
