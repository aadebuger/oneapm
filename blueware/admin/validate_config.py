from __future__ import print_function

from blueware.admin import command, usage

def _run_validation_test():
    import time

    from blueware.agent import (background_task, error_trace,
            external_trace, function_trace, wsgi_application,
            add_custom_parameter, record_exception, application)

    @external_trace(library='test',
            url='http://localhost/test', method='GET')
    def _external1():
        time.sleep(0.1)

    @function_trace(label='label',
            params={'fun-key-1': '1', 'fun-key-2': 2, 'fun-key-3': 3.0})
    def _function1():
        _external1()

    @function_trace()
    def _function2():
        for i in range(10):
            _function1()

    @error_trace()
    @function_trace()
    def _function3():
        add_custom_parameter('txn-key-1', 1)

        _function4()

        raise RuntimeError('This is a test error and can be ignored.')

    @function_trace()
    def _function4(params=None, application=None):
        try:
            _function5()
        except:
            record_exception(params=(params or {
                    'err-key-2': 2, 'err-key-3': 3.0}),
                    application=application)

    @function_trace()
    def _function5():
        raise NotImplementedError(
                'This is a test error and can be ignored.')

    @wsgi_application()
    def _wsgi_application(environ, start_response):
        status = '200 OK'
        output = 'Hello World!'

        response_headers = [('Content-type', 'text/plain'),
                            ('Content-Length', str(len(output)))]
        start_response(status, response_headers)

        for i in range(10):
            _function1()

        _function2()

        time.sleep(1.0)

        try:
            _function3()
        except Exception:
            pass

        return [output]

    @background_task()
    def _background_task():
        for i in range(10):
            _function1()

        _function2()

        time.sleep(0.5)

        try:
            _function3()
        except Exception:
            pass

    def _start_response(*args):
        pass

    _environ = { 'SCRIPT_NAME': '', 'PATH_INFO': '/test',
                 'QUERY_STRING': 'key=value' }

    _iterable = _wsgi_application(_environ, _start_response)
    _iterable.close()

    _background_task()

    _function4(params={'err-key-4': 4, 'err-key-5': 5.0},
               application=application())

_user_message = """
Running Python agent test.

Any significant errors in performing the test will be shown below. If no
errors occurred in the execution of this script and data is still not
reporting through to the UI against the application:

  %(app_name)s

after 5 minutes then check the log file:

  %(log_file)s

for debugging information. Supply the log file to blueware support if
requesting help with resolving any issues with the test not reporting
data to the blueware UI.
"""

@command('validate-config', 'config_file [log_file]',
"""Validates the syntax of <config_file>. Also tests connectivity to
blueware core application by connecting to the account corresponding to the
license key listed in the configuration file, and reporting test data under
the application name 'Python Agent Test'.""")
def validate_config(args):
    import os
    import sys
    import logging
    import time

    if len(args) == 0:
        usage('validate-config')
        sys.exit(1)

    from blueware.agent import (global_settings, initialize,
            register_application)

    if len(args) >= 2:
        log_file = args[1]
    else:
        log_file = '/tmp/python-agent-test.log'

    log_level = logging.DEBUG

    try:
        os.unlink(log_file)
    except Exception:
        pass

    config_file = args[0]
    environment = os.environ.get('BLUEWARE_ENVIRONMENT')

    if config_file == '-':
        config_file = os.environ.get('BLUEWARE_CONFIG_FILE')

    initialize(config_file, environment, ignore_errors=False,
            log_file=log_file, log_level=log_level)

    _logger = logging.getLogger(__name__)

    _logger.debug('Starting agent validation.')

    _settings = global_settings()

    app_name = os.environ.get('BLUEWARE_TEST_APP_NAME', 'Python Agent Test')

    _settings.app_name = app_name
    _settings.transaction_tracer.transaction_threshold = 0
    _settings.shutdown_timeout = 30.0

    _settings.debug.log_malformed_json_data = True
    _settings.debug.log_data_collector_payloads = True
    _settings.debug.log_transaction_trace_payload = True

    print(_user_message % dict(app_name=app_name, log_file=log_file))

    _logger.debug('Register test application.')

    _logger.debug('Collector host is %r.', _settings.host)
    _logger.debug('Collector port is %r.', _settings.port)

    _logger.debug('Proxy scheme is %r.', _settings.proxy_scheme)
    _logger.debug('Proxy host is %r.', _settings.proxy_host)
    _logger.debug('Proxy port is %r.', _settings.proxy_port)
    _logger.debug('Proxy user is %r.', _settings.proxy_user)

    _logger.debug('SSL enabled is %r.', _settings.ssl)

    _logger.debug('License key is %r.', _settings.license_key)

    _timeout = 30.0

    _start = time.time()
    _application = register_application(timeout=_timeout)
    _end = time.time()

    _duration = _end - _start

    if not _application.active:
        _logger.error('Unable to register application for test, '
            'connection could not be established within %s seconds.',
            _timeout)
        return

    if hasattr(_application.settings, 'messages'):
        for message in _application.settings.messages:
            if message['message'].startswith('Reporting to:'):
                parts = message['message'].split('Reporting to:')
                url = parts[1].strip()
                print('Registration successful. Reporting to:')
                print()
                print('  %s' % url)
                print()
                break

    _logger.debug('Registration took %s seconds.', _duration)

    _logger.debug('Run the validation test.')

    _run_validation_test()
