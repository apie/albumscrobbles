import threading


class JobsSynchronizer:
    """
    https://www.techcoil.com/blog/how-to-use-threading-condition-to-wait-for-several-flask-apscheduler-one-off-jobs-to-complete-execution-in-your-python-3-application/
    """

    def __init__(self, num_tasks_to_complete):
        assert num_tasks_to_complete > 0
        self.condition = threading.Condition()
        self.current_completed = 0
        self.status_list = []
        self.num_tasks_to_complete = num_tasks_to_complete

    def notify_task_completion(self, status_to_report=None):
        with (self.condition):
            self.current_completed += 1
            if status_to_report is not None:
                self.status_list.append(status_to_report)
            # Notify waiting thread
            if self.current_completed == self.num_tasks_to_complete:
                self.condition.notify()

    def wait_for_tasks_to_be_completed(self):
        with (self.condition):
            self.condition.wait()

    def get_status_list(self):
        return self.status_list
