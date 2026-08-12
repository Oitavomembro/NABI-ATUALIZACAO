# Política de diagnóstico

## Objetivo

Registrar contexto técnico suficiente para investigação sem expor credenciais ou transformar falhas internas em novas falhas da aplicação.

## Formato

- Timestamp.
- Nível.
- Versão do NabiCode.
- Perfil de runtime.
- Módulo/logger.
- Operação descrita pela mensagem.
- Tipo, mensagem e traceback da exceção quando disponíveis.

## Proteção de dados

- Valores associados a `senha`, `password`, `token`, `api_key` e `chave privada` são substituídos por `<omitido>`.
- Blocos de chave privada são removidos integralmente.
- Não registrar certificados privados, dados financeiros completos ou informações pessoais sem necessidade operacional.

## Retenção

- Arquivo ativo limitado a 2 MiB.
- Cinco arquivos rotacionados.
- UTF-8.
- Falha de escrita ou rotação não interrompe a aplicação.

## Interface

- Mensagens amigáveis existentes permanecem separadas do traceback técnico.
- Nem toda exceção gera popup.
- Exceções relevantes em operações persistentes devem usar `logger.exception` no limite responsável.
