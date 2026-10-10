# easyocr_values holds no model: it is the shared reader for the numbers the
# service sends, and it is imported first so the model modules stay independent.
from . import easyocr_values
from . import easyocr_document
from . import easyocr_reprocess_wizard
from . import easyocr_reading_result
from . import easyocr_extractor
from . import easyocr_batch
from . import easyocr_inbox
from . import easyocr_template
from . import easyocr_webhook_log
from . import easyocr_admin
from . import res_company
from . import res_config_settings
