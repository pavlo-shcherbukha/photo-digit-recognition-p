"""UPS-S3 Runner
   Запускає обробку моніторингу стану UPS-S3.
"""

import ups_worker.ups_wrkr as worker


if __name__ == "__main__":
    worker.main()
