# coding=utf-8
from HTMLParser import HTMLParser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html5lib.sanitizer import HTMLSanitizerMixin

import mandrill
import settings

__author__ = 'gabriel.pereira'


class DriverMandrill(object):
    mandrill_client = None

    def __init__(self):
        pass

    def get_instance(self):
        if self.mandrill_client is None:
            import mandrill
            self.mandrill_client = mandrill.Mandrill(settings.MANDRIL_APIKEY)

    def send_mail(self, from_email, to_email, subject, body, options=None):
        if not options:
            options = []
        try:
            template_name = None
            template_content = None
            async = False
            ip_pool = None
            send_at = None

            if from_email is None or from_email == '':
                from_email = settings.MAIL_FROM_ADDRESS

            # message structure
            message = {
                'html': body,
                'text': body,
                'subject': subject,
                'from_email': from_email,
                'to': []
            }

            # Parse e-mails that will receive the message
            if isinstance(to_email, dict) and len(to_email) <= 3:
                message['to'] = [to_email]
            elif isinstance(to_email, list):
                message['to'] = to_email
            elif isinstance(to_email, basestring):
                message['to'] = [{'email': to_email}]
            else:
                raise Exception('Unable to parse e-mail to')

            # Parse options
            if len(options) > 0:
                for option in options:
                    if option == 'template_name':
                        template_name = options[option]
                    elif option == 'template_content':
                        template_content = options[option]
                    elif option == 'ip_pool':
                        ip_pool = options[option]
                    elif option == 'async':
                        async = options[option]
                    elif option == 'send_at':
                        send_at = options[option]
                    else:
                        message[option] = options[option]

            self.get_instance()

            if template_name is None and template_content is None:
                result = self.mandrill_client.messages.send(message=message, async=async,
                                                            ip_pool=ip_pool, send_at=send_at)
            else:
                result = self.mandrill_client.messages.send_template(template_name=template_name,
                                                                     template_content=template_content, message=message)

        except mandrill.Error, e:
            print result
            return dict(status='NOK', message='[ERROR] Problem to send mail with mandrill : ' + str(e))

        else:
            print result
            return dict(status='OK', message=result)


class DriverSmtp(object):
    smtp_client = None

    def __init__(self):
        self.config = None

    def send_mail(self, from_email, to_email, subject, body, options=None):
        if not options:
            options = []
        try:
            if from_email is None or from_email == '':
                from_email = settings.MAIL_FROM_ADDRESS

            self.get_instance()

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = to_email

            # html detect
            if is_html(body) is True:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body))

            self.smtp_client.sendmail(from_email, to_email, msg.as_string(), options)
            self.smtp_client.close()

        except Exception, e:
            return dict(status='NOK', message='[ERROR] Problem to send mail with smtp : ' + str(e))
        else:
            return dict(status='OK', message='E-mail sent.')

    def get_instance(self):
        if self.smtp_client is None:
            import smtplib
            if settings.MAIL_PORT is not None and settings.MAIL_PORT != '':
                self.smtp_client = smtplib.SMTP(settings.MAIL_HOST, settings.MAIL_PORT)
            else:
                self.smtp_client = smtplib.SMTP(settings.MAIL_HOST)

            # TLS
            if settings.MAIL_TLS is True:
                self.smtp_client.starttls()

            self.smtp_client.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)


class TestHTMLParser(HTMLParser):

    def error(self, message):
        pass

    def __init__(self, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)

        self.elements = set()

    def handle_starttag(self, tag, attrs):
        self.elements.add(tag)

    def handle_endtag(self, tag):
        self.elements.add(tag)


def is_html(text):
        elements = set(HTMLSanitizerMixin.acceptable_elements)

        parser = TestHTMLParser()
        parser.feed(text)

        return True if parser.elements.intersection(elements) else False
