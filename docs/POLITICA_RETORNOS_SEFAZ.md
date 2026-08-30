# Política segura de retornos SEFAZ

## Princípio

O catálogo oficial pode receber códigos novos. O NabiCode não transforma código
desconhecido em autorização para reenviar: retorno não classificado exige análise
manual/consulta oficial e permanece fail-closed.

## Ações de autorização

| Categoria | Códigos inicialmente cobertos | Ação |
|---|---:|---|
| Autorizado | 100, 150 | persistir protocolo e concluir |
| Serviço temporariamente indisponível | 108, 109 | aguardar; não criar outra venda/numeração |
| Consultar antes de retransmitir | 105, 204, 539 | consultar recibo/chave; não reenviar cegamente |
| Correção controlada da mesma NF-e | 217, 297, 719 | preservar venda, chave e numeração; corrigir causa comprovada |
| Série incompatível | 244 | bloquear reenvio da mesma chave; corrigir série e exigir recuperação fiscal controlada |
| Uso denegado | 110, 301, 302, 303 | terminal; não reenviar, cancelar ou reutilizar número |
| Demais rejeições/códigos novos | qualquer outro | revisão manual e regra oficial; botão de reenvio oculto |

`217` só permite nova autorização após a consulta oficial confirmar que a NF-e
não consta na base. `297` renova exclusivamente o XMLDSig rejeitado. `719` só
insere o destinatário oficial de teste no ambiente de HOMOLOGAÇÃO e exige nome e
endereço; em PRODUÇÃO, NF-e 55 exige cliente identificado com CPF/CNPJ e endereço
fiscal completo.

`244` muda um componente da chave de acesso. Por isso nunca entra na correção
automática da mesma NF-e: a venda permanece fiscal/rejeitada, o reenvio fica
oculto e a série precisa ser corrigida antes de uma recuperação dedicada.

## Falhas sem resposta conclusiva

Timeout, queda de conexão ou interrupção depois do início da transmissão ficam
em `RESPOSTA_DESCONHECIDA`. A ação permitida é consulta/reconciliação. Nunca se
cria outra venda e nunca se retransmite antes de conhecer a situação da chave.

## Eventos e operações diferentes

Autorização, consulta, recibo, cancelamento e inutilização possuem conjuntos de
sucesso próprios já tratados pelo serviço fiscal. Um código aceito para uma
operação não deve ser reutilizado como sucesso em outra. Ampliações deste
catálogo exigem fonte oficial vigente e teste correspondente.

## Fontes oficiais

- Manual de Orientação do Contribuinte, regras de validação NF-e/NFC-e;
- Nota Técnica 2013.005: grupo `dest` obrigatório no modelo 55 (cStat 719), nome
  obrigatório (724) e endereço obrigatório (726);
- Portal Nacional da NF-e e notas técnicas vigentes.
