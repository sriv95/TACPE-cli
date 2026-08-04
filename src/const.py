import os

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("TACPE_BASE_URL", "https://ta.cpe.eng.cmu.ac.th")
TEST_URL = f"{BASE_URL}/api/user/getWithSession"
REG_TIME_URL = f"{BASE_URL}/api/regTime/list"
TA_LIST_URL = f"{BASE_URL}/api/ta/listByCmuAccount"
WORK_REPORT_URL = f"{BASE_URL}/api/workReport/get"
ADD_WORK_URL = f"{BASE_URL}/api/workReport/addWork"
EDIT_WORK_URL = f"{BASE_URL}/api/workReport/editWork"
DELETE_WORK_URL = f"{BASE_URL}/api/workReport/deleteWork"
