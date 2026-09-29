from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion leida de variables de entorno. Ningun valor sensible vive en el codigo."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "local"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    APP_NAME: str = "plataforma"
    APP_VERSION: str = "0.1.0"
    GIT_COMMIT: str = "dev"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./dev.db"

    JWT_SECRET: str = "cambiar-en-produccion"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    CORS_ORIGINS: str = "http://localhost:5173"

    # Implementaciones de los dos puertos del UML
    PREPARADOR: str = "reglas"  # PreparadorIA: "reglas" o "llm"
    EVALUADOR: str = "simulado"  # EvaluadorAislado: "simulado" o "e2b"

    # Proveedor de LLM con API compatible con OpenAI (/chat/completions). Por defecto Groq, que
    # tiene capa gratuita sin tarjeta. Gemini funciona igual cambiando la URL base a
    # https://generativelanguage.googleapis.com/v1beta/openai y el modelo a uno de Gemini.
    # Sin LLM_API_KEY, el juez, el tutor, la defensa y el preparador caen a su version por
    # reglas y lo declaran en la respuesta: nada finge haber consultado un modelo.
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TIMEOUT_S: float = 40.0
    # Modelos a probar, en orden, si el principal falla (limite de uso, caida, respuesta invalida).
    # En Groq cada modelo tiene su propia cuota, asi que uno pequeno sirve de respaldo real.
    LLM_MODELOS_RESPALDO: str = "llama-3.1-8b-instant"
    # Limite de caracteres de codigo que se envia al modelo en una sola peticion.
    LLM_MAX_CODIGO: int = 24000
    # Solo la necesita EVALUADOR=e2b. Vacia con el evaluador simulado, que no sale a la red.
    E2B_API_KEY: str = ""
    # Techo de una evaluacion completa (procedimiento, seccion 7). Pasado este tiempo la evaluacion
    # se cierra en ERROR_TECNICO aunque el proveedor no conteste: nunca queda EN_EJECUCION.
    LIMITE_EVALUACION_S: int = 240

    PREFIJO_CREDENCIAL: str = "SH"
    URL_BASE_VERIFICACION: str = "http://localhost:5173/#/credenciales"
    SEED_ON_START: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
