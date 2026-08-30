from services.sefaz_response_policy import SefazAction, SefazResponsePolicy


def test_autorizacao_indisponibilidade_duplicidade_correcao_e_denegacao():
    assert SefazResponsePolicy.decide("100").action is SefazAction.AUTHORIZED
    assert SefazResponsePolicy.decide("108").action is SefazAction.WAIT_AND_RETRY
    assert SefazResponsePolicy.decide("204").action is SefazAction.QUERY_BEFORE_RETRY
    assert SefazResponsePolicy.decide("297").allows_resend
    assert SefazResponsePolicy.decide("719").allows_resend
    assert SefazResponsePolicy.decide("301").action is SefazAction.TERMINAL_DENIAL


def test_codigo_novo_ou_desconhecido_falha_fechado_sem_reenvio():
    decision = SefazResponsePolicy.decide("1234: retorno futuro")
    assert decision.action is SefazAction.MANUAL_REVIEW
    assert not decision.allows_resend


def test_rejeicao_244_exige_nova_serie_sem_reenviar_a_mesma_chave():
    decision = SefazResponsePolicy.decide("244")
    assert decision.action is SefazAction.MANUAL_REVIEW
    assert not decision.allows_resend
    assert "não reenvie a mesma chave" in decision.operator_message
