# Teste de máquina limpa offline — NabiCode 2.5.1

Checkpoint 29  
Status: **PENDENTE DE VALIDAÇÃO FÍSICA**

## Pré-condições

- Windows 10 ou 11 x64 limpo e suportado;
- internet desconectada antes de copiar o instalador;
- sem Python, pip, Git, Visual Studio/Build Tools ou bibliotecas NabiCode;
- snapshot/VM descartável ou máquina dedicada;
- impressora térmica 80 mm e driver disponíveis para a etapa física;
- pendrive com Setup, arquivo `.sha256` e este checklist.

## Registro do ambiente

- edição/build do Windows: ____________________
- arquitetura: ____________________
- usuário/admin usado: ____________________
- impressora/driver: ____________________
- SHA-256 do Setup conferido: ____________________
- data e executor: ____________________

## Checklist obrigatório

| # | Procedimento | Resultado/evidência |
| ---: | --- | --- |
| 1 | Desconectar internet e confirmar ausência de rede | PENDENTE |
| 2 | Copiar Setup do pendrive e conferir SHA-256 | PENDENTE |
| 3 | Executar Setup e instalar sem download | PENDENTE |
| 4 | Confirmar atalhos e entrada de desinstalação | PENDENTE |
| 5 | Iniciar o NabiCode | PENDENTE |
| 6 | Confirmar `%APPDATA%\NabiCode\Producao` e banco fora de Program Files | PENDENTE |
| 7 | Fechar e abrir novamente | PENDENTE |
| 8 | Confirmar persistência | PENDENTE |
| 9 | Tentar segunda instância e confirmar bloqueio | PENDENTE |
| 10 | Abrir Dashboard, Produtos, Clientes, Histórico e Financeiro | PENDENTE |
| 11 | Abrir PDV e pesquisar/navegar por teclado | PENDENTE |
| 12 | Executar e finalizar venda | PENDENTE |
| 13 | Imprimir cupom 80 mm | PENDENTE |
| 14 | Confirmar corte físico | PENDENTE |
| 15 | Reimprimir | PENDENTE |
| 16 | Testar recebimento/financeiro e PDF sob demanda | PENDENTE |
| 17 | Criar e validar backup | PENDENTE |
| 18 | Desinstalar e confirmar preservação do AppData | PENDENTE |
| 19 | Reinstalar offline | PENDENTE |
| 20 | Confirmar recuperação automática dos dados existentes | PENDENTE |

## Critérios de reprovação

- qualquer tentativa de acesso à internet;
- pedido de instalação de Python/pip/compilador;
- DLL ou import ausente;
- escrita obrigatória em Program Files após instalação;
- perda/alteração do banco durante uninstall/reinstall;
- falha de lock, impressão, corte ou persistência;
- Setup sem hash/versão correspondentes.

## Evidências a guardar

- log do Inno Setup;
- `manifest.json` e `SHA256SUMS.txt` do onedir;
- trace JSON de startup empacotado;
- captura dos diretórios `{app}` e AppData;
- mensagem da segunda instância;
- comprovante físico de impressão/corte;
- hash do banco antes/depois de uninstall/reinstall quando nenhuma operação de negócio ocorrer.

## Declaração

Este protocolo foi preparado, mas **nenhuma máquina Windows limpa foi usada nesta sessão**. O checkpoint não está fisicamente aprovado.

## Arquivos alterados

- `TESTE_MAQUINA_LIMPA_OFFLINE_2_5_1.md`.
