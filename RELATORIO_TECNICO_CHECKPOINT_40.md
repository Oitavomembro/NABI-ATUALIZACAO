# Relatório técnico — Checkpoint 40

Data: 2026-08-09  
Base: `NabiCode_v2_5_1_DEV_CHECKPOINT_39_AUDITORIA_NOTURNA.zip`  
Estado: **NabiCode 2.5.1 DEV — aguardando nova validação física Windows**.

## Resultado executivo

Foram corrigidos somente os problemas demonstrados na validação Windows: fidelidade do splash, minimização do PDV, separação entre edição e remoção do item, estado de foco do campo Produto/código de barras e bloqueio seguro de instalação/desinstalação enquanto o NabiCode estiver aberto. Não houve alteração de regra comercial, licença, banco/schema, venda finalizada, financeiro, estoque, impressão ou corte.

Resultado automatizado final: `990 passed, 22 subtests passed`. Stress, benchmark e soak foram aprovados. A validação visual, o instalador recompilado e os dispositivos físicos continuam pendentes no Windows.

## Causas comprovadas

- Splash: o runtime anterior reimplementava em Tk/Pillow um protótipo Pygame; parâmetros isolados eram semelhantes, mas as primitivas, ordem de desenho, máscara, paleta e dinâmica não eram as mesmas.
- Minimização do PDV: a janela era marcada `transient`, condição que pode retirar o controle nativo de minimizar no Windows; não existia ação dedicada no cabeçalho.
- Carrinho: o duplo clique estava ligado diretamente à remoção, uma ação destrutiva ambígua.
- Campo Produto/código de barras: havia apenas configuração de cores. A seleção do conteúdo não respeitava integralmente o callback interno de foco/placeholder do `CTkEntry`, podendo deixar o texto com aparência de placeholder e a primeira entrada sem processamento correto.
- Desinstalação: `CloseApplications=yes` não fornecia um contrato de identidade estável com o processo. O instalador não tinha `AppMutex`, portanto podia avançar enquanto o programa ainda mantinha arquivos carregados.
- Notificações: a implementação declara e usa histórico em memória (`deque`). O vazio após reabrir/reinstalar é comportamento de sessão, não perda causada pelo desinstalador.

## Soluções aplicadas

- O motor `splash_deep_trust_engine.py` é byte a byte idêntico ao protótipo aprovado; o adaptador mantém somente lifecycle, readiness, modais, métricas e cleanup.
- O PDV continua filho da aplicação, porém deixa de ser `transient`; ganhou botão explícito “Minimizar”. F1–F11 existentes não foram remapeados.
- Duplo clique abre “Editar item da venda”. O editor altera somente quantidade, preço base e desconto da linha; usa `Decimal`, recalcula subtotal/total e nunca grava cadastro de produto.
- Clique direito oferece “Remover item”, com confirmação explícita.
- O campo de produto ganhou máquina de foco reutilizável, seleção do texto anterior, cor ativa e preservação do callback interno do `CTkEntry` e do controlador único de Enter/leitor.
- Aplicativo e Inno Setup compartilham `NabiCodeApplicationMutex`. Não há `taskkill`: o instalador solicita encerramento, e o aplicativo libera o mutex somente ao final do cleanup.
- `UninstallLogMode=append` preserva o histórico de arquivos de uma atualização sobre a mesma instalação. Nenhuma diretiva apaga `%APPDATA%\NabiCode`.
- Foi preparada configuração opcional para `build_tools/resources/NabiCode.ico`; a ausência do ícone não bloqueia o build e nenhum ícone foi criado ou integrado.

## Splash canônico

`splash_deep_trust_engine.py` e `build_tools/references/splash_nabicode_deep_trust_fluid.py` possuem o mesmo SHA-256:

`7057bd3b41ba0cca3fc05486e07f2556debdb3942cb2304b46ce18a3814ac53f`

O teste headless do helper executou 757 frames em 12,2 s, mediu 61,851 FPS, render médio de 10,508 ms e pior frame de 23,942 ms, sem erro. Isso valida continuidade lógica, não substitui a aprovação visual física Windows.

## Build e perfis

- auditoria local: `{"ok": true, "version": "2.5.1", "distribution": "NabiCode_v2_5_1"}`;
- perfil fonte: `TESTE`;
- perfil do artefato: `PRODUCAO`;
- versão: `2.5.1`;
- PyInstaller/Inno não executados neste ambiente Linux;
- wheelhouse não integra o ZIP DEV e deve ser preparado/reutilizado no Windows.

## Limites e riscos residuais

- Minimizar nativo e botão, menu de contexto, foco com leitor físico, visual do splash, DPI/Alt+Tab e mutex do Inno exigem teste instalado no Windows.
- O histórico de notificações permanece intencionalmente efêmero por sessão. Torná-lo persistente seria funcionalidade nova e requer decisão posterior.
- Impressão 80 mm, corte e teste em VM Windows limpa permanecem pendentes.
- O setup recompilado não é declarado aprovado por esta execução Linux.

Nenhuma promoção para RELEASE foi realizada.
