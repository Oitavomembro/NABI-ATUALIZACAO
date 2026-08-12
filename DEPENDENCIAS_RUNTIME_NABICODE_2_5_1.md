# Dependências de runtime — NabiCode 2.5.1 DEV

Checkpoint 22  
Data: 08/08/2026  
Status: **AUDITORIA CONCLUÍDA**

## Método

Foram auditados todos os arquivos Python do projeto por AST, além de buscas específicas por imports condicionais, imports em funções, caminhos de arquivos, recursos do PyInstaller e chamadas do Windows. `requirements.txt` foi usado somente como evidência complementar.

O baseline histórico informa Python 3.14.6 no ambiente Windows aprovado. O ambiente Linux desta auditoria não possui todas as dependências de interface/build e, por isso, suas versões instaladas não são tratadas como lock canônico de Windows.

## A. Python Standard Library

Os módulos de runtime encontrados são:

`argparse`, `atexit`, `base64`, `calendar`, `collections`, `concurrent.futures`, `contextlib`, `copy`, `csv`, `dataclasses`, `datetime`, `decimal`, `difflib`, `enum`, `hashlib`, `heapq`, `hmac`, `importlib.metadata`, `json`, `logging`, `math`, `os`, `pathlib`, `platform`, `re`, `shutil`, `socket`, `sqlite3`, `subprocess`, `sys`, `tempfile`, `textwrap`, `threading`, `time`, `tkinter`, `typing`, `unicodedata`, `urllib`, `uuid`, `weakref`, `webbrowser`, `xml.etree` e `zipfile`.

| Dependência | Origem | Uso | Obrigatória | Inclusão | Risco |
| --- | --- | --- | --- | --- | --- |
| Python 3.14.x | CPython | runtime completo | sim | embutida pelo PyInstaller | alto se a versão de build não for fixada |
| Tcl/Tk + `tkinter` | distribuição CPython | interface, diálogos, splash e CustomTkinter | sim | coletar Tcl/Tk no onedir | alto; ausência impede a UI |
| SQLite (`sqlite3`, `sqlite3.dll`) | CPython | banco local, migrações, backup e integridade | sim | coletada pelo PyInstaller | alto; validar DLL e schema |
| Bibliotecas padrão restantes | CPython | infraestrutura e regras do sistema | sim conforme uso | coletadas pelo PyInstaller | baixo/médio; imports condicionais precisam de smoke |

## B. Pacotes Python externos

| Nome | Versão/range conhecido | Onde é usado | Obrigatória | Incluir no pacote | Risco de empacotamento |
| --- | --- | --- | --- | --- | --- |
| `customtkinter` | `>=5.2,<6` | `nabicode_legacy.py`, `core/global_search.py`, `ui/theme.py` | sim | sim, pacote e dados | alto: temas/assets internos precisam ser coletados |
| `Pillow` (`PIL`) | 12.2.0 detectada nesta auditoria; **ausente do requirements direto** | `ui/background_manager.py`; dependência do CustomTkinter | sim para imagens/logo | sim | alto: `Image`, `ImageTk` e DLLs/formats podem faltar |
| `requests` | `>=2.31,<3` | fluxo fiscal em `services/fiscal_service.py` | obrigatório para fiscal; app inicia com fallback controlado | sim | médio: incluir `urllib3`, `certifi`, `charset_normalizer`, `idna` |
| `cryptography` | `>=42,<47`; 46.0.0 detectada | certificados, PKCS#12, assinatura/segurança fiscal | obrigatório para fiscal | sim, inclusive bindings nativos | alto: OpenSSL/Rust bindings e DLLs |
| `lxml` | `>=5,<7`; 6.0.2 detectada | XML fiscal | obrigatório para fiscal | sim, inclusive `lxml.etree` e DLLs | alto: extensão nativa e libxml/libxslt |
| `reportlab` | `>=4,<5`; 4.4.9 detectada | PDFs, recibos, códigos/QR e relatórios | sim | sim, dados/fontes internas | médio/alto |
| `openpyxl` | `>=3.1,<4`; 3.1.5 detectada | exportação XLSX em `services/report_service.py` | obrigatória para exportar Excel | sim | médio: import tardio pode ser omitido por análise |
| `matplotlib` | `>=3.8,<4`; 3.10.8 detectada | dashboard gráfico, backend TkAgg | obrigatória para gráficos | sim, dados e backend Tk | alto: pacote volumoso, mpl-data e backend tardio |
| `pywin32` | `>=306` somente Windows | impressão RAW/A4: `win32print`, `win32ui`, `win32con` | sim para impressão física aprovada | sim, DLLs e módulos post-install | alto: módulos importados condicionalmente |
| `PyInstaller` | `>=6,<7` | somente build | não no cliente | não dentro da distribuição como ferramenta | médio: fixar junto com `pyinstaller-hooks-contrib` |

### Lacuna inequívoca do manifesto atual

`Pillow` é usado diretamente, mas não está declarado explicitamente em `requirements.txt`. Depender apenas da dependência transitiva de CustomTkinter prejudica a reprodutibilidade. O lock de build do Checkpoint 26 deverá incluí-lo explicitamente.

## C. DLLs e bibliotecas nativas

- runtime CPython e `python3*.dll` coletados pelo PyInstaller;
- `_tkinter.pyd`, Tcl/Tk e seus diretórios de scripts;
- `sqlite3.dll` e `_sqlite3.pyd`;
- DLLs/extensões de Pillow;
- `cryptography.hazmat.bindings._rust` e bibliotecas criptográficas coletadas pelos hooks;
- `lxml.etree`/extensões e dependências XML;
- DLLs do pywin32, incluindo `pywintypes` e módulos de impressão;
- extensões nativas de NumPy/Matplotlib trazidas pelas dependências do gráfico;
- possível dependência do Microsoft Visual C++ Runtime conforme o toolchain das wheels/CPython usados no build.

O build deve gerar inventário PE/DLL e executar smoke em Windows limpo. Não é seguro declarar o VC Runtime dispensável antes de inspecionar a distribuição Windows real. A Microsoft admite tanto instalação central pelo redistributable quanto implantação app-local; a decisão deverá ser tomada a partir das DLLs efetivamente exigidas pelo onedir.

## D. Assets

- Não existe diretório `assets/` na base 2.5.0.
- O logotipo de fundo/impressão é escolhido pelo usuário e seu caminho é persistido; não deve ser embutido como dado do cliente.
- Dados internos de CustomTkinter, Pillow, Matplotlib e ReportLab são assets de dependências e precisam ser coletados pelos hooks.
- O splash atual é desenhado por código; o splash Lightspeed não pertence a esta missão.

## E. Fontes

- UI: `Segoe UI`, `Arial` e `Consolas`, esperadas no Windows 10/11.
- PDFs: fontes base PDF `Helvetica`, `Times-Roman` e `Courier`.
- Não há arquivos `.ttf`/`.otf` próprios na base.
- Risco: substituição visual em edições especiais do Windows; não impede startup. Não embutir fontes Microsoft sem licença específica.

## F. Arquivos de configuração

### Imutáveis/de distribuição

- `VERSAO.txt` — versão do aplicativo e recurso obrigatório do PyInstaller.
- `PERFIL_NABICODE.txt` — perfil empacotado (`TESTE` na base recebida); precisa de decisão explícita para build de produção.
- código/schema em `database/schema_initializer.py`.

### Mutáveis/em AppData

- `%APPDATA%\NabiCode\<Perfil>\rede_local.json`;
- `%APPDATA%\NabiCode\<Perfil>\instalacao_concluida.json`;
- `%APPDATA%\NabiCode\<Perfil>\config\sistema.json`;
- banco e marcador `.profile.json`;
- logs, relatórios, diagnósticos, rollback, releases e estado/histórico de atualização.

## G. Templates

Não há templates externos obrigatórios. Recibos, relatórios e PDFs são montados por código. Modelos escolhidos pelo usuário são valores de configuração no banco.

## H. Schemas

- Schema SQLite e migrações: `database/schema_initializer.py`, `database/product_schema_migration.py` e `database/product_decimal_migration.py`.
- XML fiscal: validações e estruturas em `services/fiscal_service.py`, `services/nfe_xml_service.py` e módulos relacionados; não foi encontrado XSD externo obrigatório.
- Manifestações de update: JSON validado por `services/update_package_validation_service.py`.

## I. Impressão

| Recurso | Necessidade |
| --- | --- |
| Spooler e driver Windows da impressora | obrigatório e fornecido pelo Windows/fabricante |
| pywin32 | obrigatório para RAW 80 mm, corte ESC/POS e A4 direto |
| PowerShell | fallback de enumeração e despacho de PDF; presente no Windows 10/11 alvo |
| Associação de leitor PDF com verbos Print/PrintTo | necessária para impressão automática de PDF |
| ReportLab | geração local do PDF |
| ESC/POS suportado pela impressora/driver | necessário para corte físico |

O instalador não deve tentar instalar driver de impressora universal nem leitor PDF sem pacote/licença explícitos.

## J–L. Recursos/imports dinâmicos e condicionais

- Nenhum `importlib.import_module`, `find_spec` ou `__import__` de runtime foi encontrado.
- `importlib.metadata` é usado somente para diagnóstico de versões.
- Imports condicionais/tardios relevantes:
  - pywin32 dentro das funções de impressão;
  - ReportLab dentro da geração de documentos;
  - OpenPyXL dentro da exportação XLSX;
  - Matplotlib/TkAgg ao abrir o dashboard gráfico;
  - Pillow ao renderizar o logotipo;
  - Requests/Cryptography/lxml/ReportLab protegidos no carregamento fiscal;
  - `nabicode_legacy` carregado depois do runtime profile em `main.py`;
  - splash executado em subprocesso pelo mesmo executável congelado.

Esses imports devem constar como `hiddenimports`/coletas explícitas e ser testados a partir do onedir.

## M. Caminhos calculados em runtime

- programa: `sys.executable.parent` quando congelado;
- recursos: `sys._MEIPASS`/diretório de source;
- dados: `NABICODE_APP_DIR`, derivado de `%APPDATA%\NabiCode\Producao|Teste`;
- banco local: dentro do AppData do perfil;
- banco de rede: caminho configurado pelo usuário;
- temporários do splash: `%TEMP%`;
- impressão/logo: caminho escolhido pelo usuário;
- relatórios/importações, backups e PDFs: auditoria do Checkpoint 24 necessária, pois ainda existem constantes/caminhos relativos no legado.

## Riscos para máquina limpa

1. Build realizado fora do Windows não produz executável Windows válido; PyInstaller não é cross-compiler.
2. Imports tardios podem não ser descobertos automaticamente.
3. Tcl/Tk, customtkinter e mpl-data precisam de validação explícita no manifesto.
4. pywin32 e suas DLLs são críticos para a impressão já aprovada.
5. Pillow não está explicitamente no requirements da base.
6. O VC Runtime somente pode ser classificado após inspeção do onedir Windows.
7. Caminhos relativos de backup/PDF/relatórios podem apontar para `{app}` sob Program Files; serão corrigidos no Checkpoint 24 com testes.
8. Uma associação de PDF ausente pode afetar impressão automática de PDF, embora cupom RAW use spooler/pywin32.

## Política para o cliente offline

Todas as dependências de runtime devem estar dentro do onedir e do instalador. O cliente não executará Python, pip, Git ou compilador e não baixará componentes. Dependências de build ficam somente na máquina de build.

## Fontes técnicas consultadas

- PyInstaller: changelog e documentação oficial de instalação/compatibilidade.
- Microsoft: redistribuição do Visual C++ Runtime e implantação app-local.
- Inno Setup: documentação oficial das seções Setup/Files/Icons/Run.

## Arquivos alterados neste checkpoint

- `DEPENDENCIAS_RUNTIME_NABICODE_2_5_1.md` — relatório novo.

Nenhum arquivo funcional foi alterado.
