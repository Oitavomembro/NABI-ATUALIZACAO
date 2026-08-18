import os

import pytest

from services.windows_data_protector import WindowsDataProtector


@pytest.mark.skipif(os.name != "nt", reason="DPAPI existe somente no Windows")
def test_dpapi_protege_e_recupera_no_usuario_atual():
    protector = WindowsDataProtector()
    secret = b"segredo-fiscal-temporario"
    protected = protector.protect(secret)
    assert protected != secret
    assert secret not in protected
    assert protector.unprotect(protected) == secret
