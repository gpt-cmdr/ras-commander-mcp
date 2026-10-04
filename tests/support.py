import time


def slow_query(connection, *args):
    time.sleep(60)


def partial_package_query(connection):
    # Deliberately no complete result: parent deadline must terminate the child.
    time.sleep(60)


def eof_query(connection, *args):
    connection.close()
