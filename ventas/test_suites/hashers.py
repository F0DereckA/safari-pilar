from django.contrib.auth.hashers import PBKDF2PasswordHasher


class FastTestPBKDF2PasswordHasher(PBKDF2PasswordHasher):
    """
    Hasher PBKDF2-SHA256 de iteración mínima exclusivo para el runner de pruebas (`IS_TEST_RUNNER=True`).
    Conserva el algoritmo y prefijo oficial `pbkdf2_sha256$` evitando ~230 ms de CPU por usuario en fixtures.
    """

    iterations = 1
