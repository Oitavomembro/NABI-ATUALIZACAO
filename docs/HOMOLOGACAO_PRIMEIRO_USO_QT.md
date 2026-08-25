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

## Roteiro humano curto

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

O instalador final e sua homologação física continuam etapas posteriores.
