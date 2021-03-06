# coding=utf-8
import settings

__author__ = 'gabriel.pereira'


class SendMail(object):
    def __init__(self, driver=None):
        if driver is None:
            self.driver = settings.MAIL_DRIVER
        else:
            self.driver = driver

        if self.driver == 'smtp':
            from driversemail import DriverSmtp
            self.dispatcher = DriverSmtp()

        elif self.driver == 'mandrill':
            from driversemail import DriverMandrill
            self.dispatcher = DriverMandrill()
        else:
            raise Exception('No mail driver found')

    def send_mail(self, from_email, to_email, subject, body, options=None):
            if not options:
                options = []
            return self.dispatcher.send_mail(from_email, to_email, subject, body, options)
