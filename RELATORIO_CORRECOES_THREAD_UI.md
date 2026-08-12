# Relatório de correções da thread da UI

## Alterações funcionais

Nenhuma. A auditoria não encontrou problema concreto que pudesse ser corrigido com segurança sem medição real ou sem reabrir atomicidade/navegação já aprovadas.

## Contratos confirmados

- Tk/CTk permanece manipulado na thread principal.
- Cliente usa worker somente para consulta e conexão SQLite própria.
- Retorno ao Tk usa `after(0)` e descarta carga obsoleta.
- Pesquisa, resize e background possuem debounce.
- Não existe `check_same_thread=False`.
- Impressão 80 mm, PDF sob demanda e reimpressão permanecem intactos.

## Pendências controladas

Instrumentar em ambiente real, antes de qualquer mudança, duração de backup automático, consultas em rede, importações e geração documental. Só então desenhar workers com encerramento e retorno seguros.
