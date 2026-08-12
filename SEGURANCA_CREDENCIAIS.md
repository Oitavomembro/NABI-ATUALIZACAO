# Segurança de credenciais

## Escopo da inspeção

Foi inspecionado `services/security_service.py` e seu uso na aplicação, nos testes e na documentação existente. Nenhuma senha é reproduzida neste documento.

## Conclusão

O valor `MASTER_PASSWORD_SHA256` é o hash SHA-256 de uma credencial mestre estática de fábrica/suporte. Ele não é apenas um exemplo: a credencial correspondente é aceita por fluxos executados pela aplicação.

A credencial mestre é usada para:

- autenticação administrativa;
- confirmação de operações protegidas;
- acesso a funções administrativas;
- desbloqueio e renovação administrativa de licença.

O hash não permite recuperar diretamente a senha, mas a base original continha a entrada correspondente em texto claro em testes de regressão. Esses testes foram saneados nesta preparação: agora usam uma credencial exclusivamente sintética e substituem temporariamente o hash somente durante o teste. O hash e o comportamento de produção não foram modificados.

Não foi encontrada indicação de que essa credencial pertença a um cliente específico. Trata-se de uma credencial global embutida no produto e usada em produção.

## Risco

Classificação: **alta** para qualquer repositório público e relevante mesmo em repositório privado.

Quem obtiver a credencial poderá alcançar fluxos administrativos e de licença protegidos pela credencial mestre. O controle de acesso ao futuro repositório privado deve ser restrito até que exista uma migração segura.

## Possibilidade de substituição segura

É tecnicamente possível retirar a credencial do código, mas isso exige uma missão funcional e de segurança própria. Uma solução futura deve considerar:

- configuração segura por instalação, sem valor secreto versionado;
- armazenamento protegido no Windows ou provisionamento controlado;
- credenciais individualizadas e revogáveis;
- rotação e trilha de auditoria;
- testes que não armazenem a credencial real em texto claro;
- comportamento seguro quando a configuração estiver ausente;
- migração controlada da credencial legada.

Variável de ambiente isoladamente não resolve distribuição, provisionamento e recuperação da credencial em instalações offline; ela pode fazer parte da solução, mas não deve ser o único mecanismo.

## Impacto em instalações existentes

O hash mestre está no código e não no banco de cada instalação. Uma atualização que simplesmente o remova ou troque altera imediatamente a credencial aceita por todas as instalações atualizadas. Isso pode quebrar login administrativo, confirmações protegidas e desbloqueio de licença, sem oferecer uma rota de recuperação.

Por compatibilidade, nenhum código de produção, hash ou fluxo foi alterado nesta preparação. Somente as fixtures dos testes que expunham a credencial foram substituídas por valores sintéticos. A correção definitiva deve prever transição versionada, provisionamento da nova credencial e retirada posterior do mecanismo legado.

## Decisão desta etapa

- não revelar a credencial;
- não alterar o hash;
- sanear os testes sem alterar a autenticação de produção;
- manter o repositório privado;
- tratar a migração como missão de segurança separada antes de qualquer abertura pública do código.
