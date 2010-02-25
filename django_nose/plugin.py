from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.core import mail
from django.test.testcases import (
    disable_transaction_methods, restore_transaction_methods)


__all__ = ('ResultPlugin', 'DjangoPlugin',)


class ResultPlugin(object):
    """
    Captures the TestResult object for later inspection.

    nose doesn't return the full test result object from any of its runner
    methods.  Pass an instance of this plugin to the TestProgram and use
    ``result`` after running the tests to get the TestResult object.
    """

    name = "result"
    enabled = True

    def finalize(self, result):
        self.result = result


class DjangoPlugin(object):
    """Replicates the functionality of Django's ``TestCase`` class.

    Ensures that after each test:

    * The database is rolled back.
    * The email outbox is reset.

    It is possible to disable transaction support (simulate the behavior
    of Django's ``TransactionTestCase`` by setting ``use_transaction`` to
    ``False`` in a nose context (i.e. can be on a class, module or package
    level).

    Not implemented is support for fixture loading and per-test urlconfs.

    The code is also loosly based on ``nosedjango``.
    """

    enabled = True
    name = "django"

    def _has_transaction_support(self, test):
        transaction_support = True
        if hasattr(test.context, 'use_transaction'):
            transaction_support = test.context.use_transaction
        if getattr(settings, 'DISABLE_TRANSACTION_MANAGEMENT', False):
            # Do not use transactions if user has forbidden usage.
            transaction_support = False
        if (hasattr(settings, 'DATABASE_SUPPORTS_TRANSACTIONS') and
            not settings.DATABASE_SUPPORTS_TRANSACTIONS):
            transaction_support = False
        return transaction_support

    def beforeTest(self, test):
        mail.outbox = []

        # Before each test, disable transaction support.
        transaction_support = self._has_transaction_support(test)
        if transaction_support:
            transaction.enter_transaction_management()
            transaction.managed(True)
            disable_transaction_methods()

    def afterTest(self, test):
        # After each test, restore transaction support, and rollback
        # the current test's transaction. If transactions are not
        # available, truncate all tables.
        transaction_support = self._has_transaction_support(test)
        if transaction_support:
            restore_transaction_methods()
            transaction.rollback()
            transaction.leave_transaction_management()
            # If connection is not closed Postgres can go wild with
            # character encodings.
            connection.close()
        else:
            call_command('flush', verbosity=0, interactive=False)