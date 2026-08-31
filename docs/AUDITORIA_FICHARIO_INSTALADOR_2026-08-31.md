# Fichário: auditoria e instalador — 31/08/2026

## Escopo e origem

Proprietário autorizou auditar cadastro/edição de clientes, fichas, vendas,
pagamentos e operações relacionadas, gerar instalador e copiá-lo ao pendrive.
Fonte exata: `2afdf5df4e8524a4f20ccfb10e2554371f59913b`, extraída por
`git archive` para `C:\NB\Fichario-2afdf5d\src`. Nenhuma mudança local de
splash/login da trilha principal entrou no build. Nenhum dado real foi usado.

## Validação

- Rodada consolidada: **464 passed, 420 subtests passed**, 43,74 s.
- Abrange todos os testes selecionados de Fichário/licença V2/emissor,
  commercial, cadastro/manutenção de clientes, recebimentos, parcelas,
  comprovantes/PDF, backup/restauração e UI comercial relacionada.
- Cadastro normalizado; ficha duplicada/nome vazio/limite negativo recusados;
  edição preserva ID, saldo e vínculos; exclusão protege registros movimentados.
- Ensaio real SQLite: venda a prazo R$ 300; recebimento R$ 150; rejeição de
  R$ 151 acima do saldo; quitação de R$ 150; parcelas/histórico/saldos conferidos.
- Vendas à vista, entrada + crediário, limites, cancelamento, falha tardia e
  rollback; revisão e confirmação, cancelamento e auto-repeat do recebimento.
- Backup/restauração em TEMP preserva fichas/valores/configurações; corrupção,
  schema incompatível e falha intermediária não destroem o banco vigente.
- `compileall`, validação oficial do build e `git diff --check` aprovados.
- Ambiente `C:\NB\BuildEnv251` coincide com todas as versões do lock;
  `pip check`: nenhuma dependência quebrada.

Evidências locais: `C:\NB\Fichario-2afdf5d\audit-tests.xml`,
`audit-tests.log`, `build-app.log` e `build-installer.log`.

## Binário e empacotamento

- Build oficial `build_tools/build_fichario.py app` e depois `installer`
  com `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`: exit 0.
- Sem instalação sobre Program Files. Smoke com APPDATA/LOCALAPPDATA isolados
  e PATH Windows, sem Python de desenvolvimento: `--license-status` retorna 3
  (ausência de licença), sem criar banco. Janela real de ativação abriu e fechou.
- Clique nativo em Copiar código da máquina: clipboard com exatamente 64 hex;
  confirmação exibida. Código compilado contém `activation_fingerprint`.
- QtWidgets/qwindows, Tcl/Tk e catálogo público presentes; catálogo coincide
  com o versionado. Não foram encontrados banco, licença de cliente, PFX ou
  chave privada na distribuição; PYZ sem módulos da Nabi ou do emissor.
- Notices e lock de dependências incluídos. Avisos de análise do PyInstaller
  preservados nos logs (incluem imports opcionais); não se afirma build sem avisos.
- Versão 2.5.2, revisão 23. Instalador **sem assinatura Authenticode**.

SHA-256 do executável:
`3529f3fc8aaf65897c9f44f3fe1a0604814b5f23f4b364b72529e13b528d19c3`

SHA-256 do instalador (121.203.334 bytes):
`c51ced3b490820d5806842c32df9cc6260a82f7485c1d6ad1b32c01795c2cfcd`

## Entrega e limites

Instalador local:
`C:\NB\Fichario-2afdf5d\src\build_output\fichario\installer\NabiCode_Fichario_2.5.2_Setup_Offline.exe`.

Pasta de entrega no pendrive NABI:
`E:\NabiCode-Fichario-2.5.2-R23-2afdf5d`, contendo instalador, LEIA-ME e
SHA256SUMS. Instalador antigo preservado; nenhuma chave ou licença copiada.

Permanecem manuais: instalação no computador de destino, emissão/ativação com
o fingerprint desse computador e impressão física. Não se afirma ausência
absoluta de defeitos nem homologação em máquina limpa real. Nenhum push.
