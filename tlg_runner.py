"""telegram Runner
   Запускає обробку повіідомлень з черги RQ для відправки в телеграм.
"""

import tlg_worker.tlg_wrkr as worker


if __name__ == "__main__":
    worker.main()
