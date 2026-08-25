# Backup criptografado V2

O formato opcional `.nabibackup` protege o banco operacional com AES-256-GCM e
uma chave derivada da senha por scrypt. O cabeçalho versionado também é
autenticado: senha incorreta, alteração, truncamento ou parâmetros inesperados
impedem a abertura.

## Limites operacionais

- A senha nunca é persistida, incluída no nome do arquivo ou registrada em log.
- Não existe senha mestra, recuperação ou conversão silenciosa. Perder a senha
  torna aquele envelope irrecuperável.
- O `.db` antigo continua compatível, mas é identificado explicitamente como
  `SQLITE_LEGACY_UNENCRYPTED`.
- O envelope contém somente o banco SQLite. O arquivo fiscal separado conserva
  seu fluxo e sua política próprios; este checkpoint não altera Fiscal/SEFAZ.
- Antes de qualquer restauração real, o envelope é autenticado e aberto somente
  em pasta temporária. Depois são executados `integrity_check`,
  `foreign_key_check` e a comparação de schema com o banco ativo.
- A verificação nunca substitui o banco ativo. A restauração destrutiva continua
  exclusivamente no serviço oficial, com confirmação e backup de segurança.

## Formatos

- `*.nabibackup`: envelope NabiCode criptografado e autenticado, versão 1.
- `*.db`: backup SQLite legado, compatível e não criptografado.

Não renomeie um `.db` para `.nabibackup`: o formato é reconhecido pelo conteúdo,
não apenas pela extensão.
