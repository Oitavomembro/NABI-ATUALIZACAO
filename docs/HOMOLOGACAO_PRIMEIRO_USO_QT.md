# Homologação do primeiro uso Qt

Este roteiro comprova a abertura desde uma máquina lógica vazia sem tocar nos
dados ativos. O ensaio usa `TEMP`, perfil `TESTE`, banco descartável, chave
Ed25519 criada somente em memória e licença temporária removida ao final. Não
carrega certificado, XML, CSC ou senha real e não acessa a SEFAZ.

## Ensaio automatizado

Execute com o Python homologado:

```powershell
& '<CAMINHO_DO_PYTHON_3.14>' build_tools\homologate_first_use.py
```

Para preservar evidências, informe uma pasta TEMP vazia:

```powershell
& '<CAMINHO_DO_PYTHON_3.14>' build_tools\homologate_first_use.py --root "$env:TEMP\NabiCode-Primeiro-Uso"
```

O arquivo `homologacao_primeiro_uso.json` registra somente estados técnicos e
caminhos do diretório descartável. Não é uma licença de cliente nem substitui a
ativação real.

## Fase A — primeiro uso comercial em TESTE

1. Instale o NabiCode em uma máquina de homologação sem copiar o banco ativo.
2. Abra o programa: sem licença, confirme que apenas ativação, diagnóstico,
   backup e exportação segura permanecem disponíveis.
3. No Emissor administrativo, emita uma licença TESTE vinculada ao código dessa
   máquina e ative o arquivo `.nabilic` recebido. Nunca copie a chave privada
   para o computador do cliente.
4. Reabra o NabiCode. Informe empresa/loja e crie o primeiro administrador com
   senha nova de pelo menos oito caracteres.
5. Confirme que o sistema solicita login; entre com o administrador criado.
6. Confirme a página Início e abra **Vendas**. Não configure nem teste Fiscal/
   SEFAZ neste roteiro.

**Critério de parada:** qualquer falha de instalação, ativação, criação do banco,
configuração inicial, criação do administrador, login, shell ou Vendas encerra a
homologação. Não inicie a preparação Fiscal para contornar uma falha da Fase A.

## Fase B — prontidão fiscal local e offline

Esta fase é posterior à aprovação completa da Fase A. Ela não transmite, não
consulta a SEFAZ e não solicita nem persiste a senha do certificado.

1. Abra o perfil empresarial e confirme razão social, CNPJ, IE, UF, município,
   código do município, regime e demais dados cadastrais aplicáveis com a fonte
   registrada.
2. Selecione exclusivamente o ambiente **HOMOLOGAÇÃO**. Produção é proibida.
3. Selecione o arquivo A1 da empresa apenas para a validação local autorizada.
   Não copie o PFX para o Git, pasta do programa, pacote de suporte ou evidência.
4. Sem informar a senha, confirme que a tela mantém o certificado como pendente
   e não alega prontidão antecipada.
5. Sem senha, valide apenas o que o arquivo permitir com segurança. Se o PFX for
   criptografado, cadeia, vigência e CNPJ permanecem **PENDENTES**; não invente
   resultado nem contorne a proteção. Essa validação será concluída localmente
   no início da Fase C, após o proprietário digitar a senha somente em memória e
   antes de qualquer rede.
6. Configure ambiente, modelo, série e numeração somente com dados de
   homologação aprovados e execute apenas o preflight local. Guarde o relatório
   redigido, sem PFX, senha, CSC, token, XML real ou dado pessoal desnecessário.

**Critério de parada:** cadastro incompleto, A1 inválido/vencido, cadeia não
confirmada, CNPJ divergente, ambiente diferente de HOMOLOGAÇÃO, série/numeração
não aprovadas ou qualquer pendência do preflight bloqueiam a Fase C. Não existe
fallback, senha mestre ou liberação manual por configuração local.

## Fase C — SEFAZ homologação manual posterior

Executar somente com o proprietário presente, credenciamento confirmado e uma
matriz de casos previamente autorizada. A senha do A1 é digitada pelo
proprietário no momento do uso e não entra em roteiro, log, print, vídeo ou
arquivo. Registrar caso, horário, resposta, chave/hash e efeitos antes/depois,
sempre redigindo segredos e dados pessoais.

1. Confirmar novamente ambiente **HOMOLOGAÇÃO**, sessão e permissão; o
   proprietário digita a senha somente em memória, conclui a validação local de
   cadeia/vigência/CNPJ e repete o preflight. Rede continua bloqueada até todos
   os requisitos ficarem aprovados.
2. Executar apenas os casos autorizados da matriz: status, rejeição controlada,
   autorização, consulta, idempotência, evento/cancelamento quando aplicável,
   timeout desconhecido, reinício e reconciliação.
3. Parar imediatamente diante de resposta inesperada, ambiente divergente,
   numeração inconsistente, efeito duplicado ou evidência insuficiente.

Produção permanece proibida em todas as fases. A aprovação da Fase C não libera
produção automaticamente; isso exige auditoria e autorização próprias.

## Critérios de aprovação

- licença ausente não cria nem abre o banco operacional;
- ativação válida libera somente os recursos assinados;
- banco novo recebe o schema atual e não nasce autenticado;
- primeiro administrador é criado uma única vez e login incorreto é recusado;
- shell e Vendas abrem e fecham sem travar;
- todos os dados mutáveis ficam fora de `Program Files`;
- catálogo público existe no pacote; chave privada nunca entra nele;
- plugins Qt de plataforma e runtime Tcl/Tk estão presentes no ambiente de build;
- nenhuma transmissão fiscal ou dado real participa do ensaio.

O instalador final e sua homologação física continuam etapas posteriores. O
runner automatizado cobre somente a Fase A e não deve ser ampliado para carregar
certificado, senha, XML ou rede.
