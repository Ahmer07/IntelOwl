import os
import re
import traceback
import requests

from celery.utils.log import get_task_logger

from api_app.exceptions import AnalyzerRunException
from api_app.script_analyzers import general
from intel_owl import settings

logger = get_task_logger(__name__)

db_name = "tor_exit_addresses.txt"
database_location = "{}/{}".format(settings.MEDIA_ROOT, db_name)


def run(analyzer_name, job_id, observable_name, observable_classification, additional_config_params):
    logger.info("started analyzer {} job_id {} observable {}"
                "".format(analyzer_name, job_id, observable_name))
    report = general.get_basic_report_template(analyzer_name)
    try:
        result = {'found': False}
        if not os.path.isfile(database_location):
            updater()

        with open(database_location, "r") as f:
            db = f.read()

        db_list = db.split('\n')
        if observable_name in db_list:
            result['found'] = True

        # pprint.pprint(result)
        report['report'] = result
    except AnalyzerRunException as e:
        error_message = "job_id:{} analyzer:{} observable_name:{} Analyzer error {}" \
                        "".format(job_id, analyzer_name, observable_name, e)
        logger.error(error_message)
        report['errors'].append(error_message)
        report['success'] = False
    except Exception as e:
        traceback.print_exc()
        error_message = "job_id:{} analyzer:{} observable_name:{} Unexpected error {}" \
                        "".format(job_id, analyzer_name, observable_name, e)
        logger.exception(error_message)
        report['errors'].append(str(e))
        report['success'] = False
    else:
        report['success'] = True

    general.set_report_and_cleanup(job_id, report, logger)

    logger.info("finished analyzer {} job_id {} observable {}"
                "".format(analyzer_name, job_id, observable_name))

    return report


def updater():

    try:
        logger.info("starting download of db from tor project")
        url = "https://check.torproject.org/exit-addresses"
        r = requests.get(url)
        r.raise_for_status()

        data_extracted = r.content.decode()
        findings = re.findall("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", data_extracted)

        with open(database_location, "w") as f:
            for ip in findings:
                if ip:
                    f.write("{}\n".format(ip))

        if not os.path.exists(database_location):
            raise AnalyzerRunException("failed extraction of tor db")

        logger.info("ended download of db from tor project")

    except Exception as e:
        traceback.print_exc()
        logger.exception(e)

    return database_location

