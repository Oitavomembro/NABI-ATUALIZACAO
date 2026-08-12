# NabiCode — Continuidade do desenvolvimento

Este repositório privado é a fonte oficial do código da frente **NabiCode — Desenvolvimento**. A branch de trabalho é `dev/nabicode-2.5.1`. A frente do instalador é separada.

## Preparar outro computador

```bash
git clone <URL-DO-REPOSITORIO-PRIVADO>
cd NabiCode-Desenvolvimento
git checkout dev/nabicode-2.5.1
git pull
```

O acesso deve ser feito somente com uma conta autorizada no repositório privado. Não reutilize a pasta de outra instalação do NabiCode como cópia de desenvolvimento.

## Antes de trabalhar

```bash
git status
git checkout dev/nabicode-2.5.1
git pull
```

Leia antes de alterar:

- `ESTADO_ATUAL.md`;
- `FRONTEIRA_INSTALADOR.md`;
- `SEGURANCA_CREDENCIAIS.md`.

Confirme que não existem bancos, backups, credenciais, `.env`, logs ou dados de clientes entre os arquivos a versionar.

## Validar alterações

Execute no mínimo:

```bash
python -m compileall .
python -m pytest
```

Testes físicos ou dependentes de Windows devem ser executados no ambiente apropriado. Não altere código apenas para mascarar incompatibilidade do ambiente de teste.

## Depois do trabalho

```bash
git status
git diff
python -m compileall .
python -m pytest
git add <arquivos-revisados>
git commit -m "Descrição objetiva da alteração"
git push
```

Antes de `git add`, revise individualmente os arquivos. Antes de `git push`, confirme a branch e o repositório remoto.

## Dados proibidos no Git

Nunca copie via Git:

- banco real do NabiCode;
- conteúdo de `%APPDATA%\NabiCode`;
- backups ou dumps;
- dados de clientes ou usuários;
- credenciais, certificados privados ou arquivos `.env`;
- logs que possam conter dados operacionais.

Fixtures sintéticas legítimas podem existir apenas em `tests/fixtures/`, após revisão para comprovar que não contêm dados reais.

