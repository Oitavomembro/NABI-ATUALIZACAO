# Validação manual Windows — Checkpoint 40

Todos os itens abaixo estão **pendentes** nesta candidata. As aprovações da rodada anterior são evidência histórica, não aprovação das novas alterações.

## Rebuild em caminho curto

Em `C:\NB\NabiCode`, com internet somente para atualizar o wheelhouse após a inclusão de `pygame-ce`:

```powershell
powershell -ExecutionPolicy Bypass -File build_tools\prepare_wheelhouse.ps1
```

Confirmar `pygame_ce-2.5.7-cp314-cp314-win_amd64.whl` e o `build_output\wheelhouse\SHA256SUMS.txt`. Em seguida desconectar a internet e executar exclusivamente:

```powershell
powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1
```

O resultado esperado continua sendo um único `build_output\installer\NabiCode_2.5.1_Setup_Offline.exe`.

## Checklist

1. Instalar o setup offline sem Python, pip ou internet.
2. Confirmar perfil PRODUCAO e recuperação do banco/configurações existentes.
3. Comparar o splash lado a lado com `splash_nabicode_deep_trust_fluid.py`: mesma composição, cores, velocidade, formação de `NABICODE`, timing e nenhum texto adicional.
4. Confirmar animação contínua, DPI correto, modal acima da splash, Alt+Tab e ausência de helper órfão.
5. Abrir o PDV; confirmar botão nativo de minimizar e botão “Minimizar”.
6. Confirmar F3 Cliente, F5 Orçamento, F7 Reabrir, F8 Pré-venda e demais atalhos anteriores.
7. Duplo clicar um item: confirmar editor “Editar item da venda”. Alterar quantidade, preço permitido e desconto; conferir subtotal/total e confirmar que o cadastro mestre não mudou.
8. Clicar com botão direito: remover somente após escolher “Remover item” e confirmar.
9. Repetir item cadastrado, item avulso, estoque insuficiente e cancelamento.
10. Clicar no campo Produto/código de barras com texto anterior; digitar e usar leitor imediatamente, sem clicar fora. Confirmar texto branco, pesquisa, sugestões, setas e Enter.
11. Com NabiCode aberto, iniciar atualização/desinstalação: o Inno deve solicitar fechamento e não concluir silenciosamente. Fechar pelo aplicativo e prosseguir.
12. Confirmar ausência de processo NabiCode e de resíduos binários pertencentes à instalação em `C:\Program Files\NabiCode` após desinstalar.
13. Confirmar preservação de `%APPDATA%\NabiCode`, banco, configuração e licença.
14. Reinstalar e confirmar recuperação dos dados operacionais.
15. Confirmar que Histórico de notificações inicia vazio por ser histórico de sessão; vendas/clientes/movimentos permanecem persistidos.
16. Testar expiração, senha errada, desbloqueio, reaparecimento da UI, reabertura e segunda instância.
17. Executar venda, orçamento, reabertura, cancelamento, recebimento e persistência.
18. Testar impressão física 80 mm e corte físico.
19. Repetir instalação/desinstalação/reinstalação em VM Windows limpa e fisicamente offline.

## Evidência anterior já aprovada no Windows

Setup offline, abertura em PRODUCAO, single-instance, venda, item avulso, finalização, clientes, recebimento, saldo, cancelamento/reversão, histórico de venda, orçamento F5, reabertura F7 e preservação/recuperação do banco em AppData.

## Ainda pendente

Nova validação visual do splash, todas as alterações deste checkpoint, impressão/corte físicos e VM Windows limpa.
