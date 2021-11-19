import pytz
from configuration import configs

PNG_MIME_TYPE = 'image/png'
PDF_MIME_TYPE = 'application/pdf'

DEFAULT_TZ = configs['timezone']
LOCAL_TZ = pytz.timezone(DEFAULT_TZ)
