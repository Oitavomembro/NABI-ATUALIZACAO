# NabiCode v2.4.24 — Exclusão segura de NF-e importada

Versão baseada na v2.4.23.

## Implementado

- seleção manual dos botões exibidos na navegação principal;
- opção de ocultar Início, Vendas, Clientes, Produtos e Configurações;
- atalhos F1 a F5 preservados mesmo quando o botão correspondente está oculto;
- F4 continua abrindo Produtos independentemente da configuração visual;
- aplicação imediata da visibilidade ao salvar;
- compatibilidade com os modos Simples, Intermediário e Avançado;
- compatibilidade com espaços de trabalho e menu adaptativo;
- preferências antigas migradas automaticamente sem alteração no banco.

## Executar no CMD

```cmd
py main.py
```

## Testes

```cmd
py -m unittest discover -s tests -v
```


## Excluir NF-e importadas de teste

Produtos → **Notas importadas**. A exclusão exige senha administrativa, cria snapshot e reverte o estoque antes de liberar a chave para nova importação.

## v2.4.26 — Etapa 1: PDV independente

- Vendas abre em janela própria, maximizada e sem o dashboard.
- Busca de produto recebe foco automaticamente.
- Carrinho e total permanecem visíveis durante toda a operação.
- `Del` remove o item selecionado, `F9` finaliza e `F11` alterna tela cheia.
- `Esc` fecha a janela com confirmação quando existe venda em andamento.
- Ao fechar o PDV, o carrinho é preservado para a próxima abertura.

## Modo comercial e item avulso

Em **Configurações > Modo de operação**, escolha:

- **COMERCIAL — sem emissão fiscal**: libera a caixa **Produto avulso** no PDV. O item é registrado na venda e no comprovante, mas não cria cadastro e não movimenta estoque.
- **FISCAL — com recursos fiscais**: bloqueia item avulso e exige produto cadastrado com dados fiscais.

No PDV comercial, marque **Produto avulso — não cadastra e não movimenta estoque**, informe descrição, quantidade e preço e adicione normalmente.


## Login opcional
Por padrão o NabiCode abre sem solicitar senha. Em Configurações > Segurança é possível ativar o login ao iniciar. Usuários podem ser criados com senha ou sem senha; quando o login estiver ativo, usuário sem senha entra deixando o campo de senha vazio.


## Conclusão do modo Comercial/Fiscal (2.4.33)

- O modo Comercial oculta comandos, botões e acessos diretos de NF-e/fiscal.
- O modo Fiscal mantém os recursos fiscais disponíveis e bloqueia item avulso.
- Alterar o modo exige reinicialização para reconstruir integralmente menus e telas.
- A janela de pagamento inclui a escolha de impressão antes de concluir.
- Enter avança pelo fluxo; Shift+Enter volta; a venda só é concluída no último controle.
- O teste de versão valida consistência e formato, sem congelar o projeto em uma versão antiga.

## Correções 2.4.34
- Login inicial fica desativado até ser habilitado explicitamente em Configurações > Segurança.
- Credencial mestra administrativa aceita em login e confirmações protegidas, sem texto puro no código.
- Restauração de fábrica valida senha digitada e redefine login inicial como opcional.
- Diagnóstico passa a validar a tabela real `categorias_produtos`.
- Comprovante aceita os tipos usados pelo PDV e permite CONSUMIDOR FINAL sem cliente cadastrado.
- Botão visual de suspender venda removido; atalho F6 preservado.
