from multiprocessing import Pool
import time

DELAY_TO_START_FUNCTION = 0


def call_function_with_sleep(task_argument):
    function = task_argument["function"]
    dict_arguments = task_argument["arguments"]
    try:
        time.sleep(DELAY_TO_START_FUNCTION)
        return function(**dict_arguments)
    except Exception as e:
        print(e)
        return False


def multiprocessing_function(function, list_of_dict_arguments, num_threads=1):
    tasks_arguments = [{"function": function, "arguments": dict_arguments} for dict_arguments in list_of_dict_arguments]

    if num_threads < 1:
        num_threads = 1

    with Pool(num_threads) as p:
        return p.map(call_function_with_sleep, tasks_arguments)
