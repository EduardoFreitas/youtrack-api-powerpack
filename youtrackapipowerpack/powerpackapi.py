# coding=utf-8
import re
from youtrackapipowerpack.asanautils import AsanaUtils
from youtrackapipowerpack.gitutils import GitUtils
from youtrackapipowerpack.ppemail.sendmail import SendMail
from youtrackapipowerpack.youtrackutils import YoutrackUtils
import settings

__author__ = 'gabriel.pereira'


class PowerPackApi(object):
    issue_types_deploy = ['Bug', 'Epic', 'Feature', 'Task']

    def __init__(self, args):
        print ">>> Starting with "
        print args.action
        self.youtrackUtils = YoutrackUtils()
        self.gitUtility = GitUtils()
        self.asanaUtils = AsanaUtils()
        self.load(args)

    def load(self, args):
        if args.action[0] == 'deploy':
            print ">>> Deploying ..."
            if 3 == len(args.action[1:]):
                self.deploy(args.action[1], args.action[2], args.action[3])

    def deploy(self, tag_start, tag_end, project_clone_path):

        repo_name = self.gitUtility.get_rep_name(project_clone_path)

        # Notificação de tarefas com branches fora do padrão
        self.notify_branch_developers(tag_start, tag_end, project_clone_path, repo_name)
        print ">>> notify_branch_developers"

        # Busca a lista de tarefas
        task_list = self.gitUtility.get_task_branches(tag_start, tag_end, project_clone_path)

        # Busca as tarefas no youtrack
        youtrack_filter = " ".join(str(x) for x in task_list)
        youtrack_filter += ' has: -{Subtask of}'
        issues = self.youtrackUtils.get_issues(youtrack_filter, 0, 100)

        # separa as tarefas que estão verified das que não estão
        issues_verified = [i for i in issues if i.State == 'Verified']
        issues_not_verified = [i for i in issues if i.State != 'Verified' and i.State != 'Deployed']

        # envia release notes
        self.notify_release_notes(issues, tag_end, repo_name)
        print ">>> notify_release_notes"

        # Atualiza o status das que estão verified para Deployed
        for issue in issues_verified:
            YoutrackUtils.set_issue_status(issue.id, 'Deployed')
            if hasattr(issue, 'AsanaID') and issue.AsanaID is not None:
                self.asanaUtils.send_notification(issue.AsanaID)

        # # envia e-mail informativo com as issues que não estão com status verified
        PowerPackApi.notify_to_verify(issues_not_verified, tag_end, repo_name)
        print ">>> notify_to_verify"

    def notify_branch_developers(self, tag_start, tag_end, project_clone_path, repo_name):

        git_log = self.gitUtility.get_log(tag_start, tag_end, project_clone_path)

        developers = {}
        merge_vars = []
        to_email = []

        subject = settings.MAIL_BRANCH_VERIFY_SUBJECT
        subject = str(subject).replace('{{release_tag}}', tag_end)
        subject = str(subject).replace('{{repo_name}}', repo_name)

        emails_cc = str(settings.MAIL_BRANCH_VERIFY_CC).split(';')
        from_email = settings.MAIL_FROM_ADDRESS

        # seek branches without the pattern and mount e-mail list
        for line in git_log:
            divided_line = line.split('|')
            task = re.search('([A-Z]{1,6}-(\d+){1,6})', divided_line[2])
            if task is None:
                if not developers.has_key(divided_line[1]):
                    developers[divided_line[1]] = {
                        'name': divided_line[0],
                        'branches': [],
                        'branches_formated': ''
                    }
                developers[divided_line[1]]['branches'].append(divided_line[2])
                developers[divided_line[1]]['branches_formated'] = '<br />'.join(
                    str(c) for c in developers[divided_line[1]]['branches'])

        # if hasn't a branch out of pattern just exit
        if len(developers) == 0:
            return

        # mount e-mail to list with merge vars for mandrill
        for email, developer in developers.iteritems():
            myvars = [
                {'name': 'developer_name', 'content': developer['name']},
                {'name': 'branches', 'content': developer['branches_formated']},
                {'name': 'release_tag', 'content': tag_end},
                {'name': 'repo_name', 'content': repo_name}
            ]

            to_email.append({
                'email': email,
                'type': 'to'
            })

            merge_vars.append({
                'rcpt': email,
                'vars': myvars
            })

            # inject merge vars for the cc recipients
            for emailcc in emails_cc:
                merge_vars.append({
                    'rcpt': emailcc,
                    'vars': myvars
                })

        # e-mails to be in copy
        for email in emails_cc:
            to_email.append({
                'email': email,
                'type': 'bcc'
            })

        # envia e-mail
        options = {
            'template_name': settings.MAIL_BRANCH_VERIFY_MANDRILL_TEMPLATE,
            'template_content': [],
            'merge_vars': merge_vars
        }

        mail_sender = SendMail()
        mail_sender.send_mail(from_email, to_email, subject, '', options)

    def notify_release_notes(self, issues, release_tag, repo_name):
        issue_types_deploy = ['Bug', 'Epic', 'Feature', 'Task', 'Exception']

        subject = settings.MAIL_DEPLOY_SUBJECT
        subject = str(subject).replace('{{release_tag}}', release_tag)
        subject = str(subject).replace('{{repo_name}}', repo_name)

        from_email = settings.MAIL_FROM_ADDRESS
        emails_cc = str(settings.MAIL_DEPLOY_CC).split(';')
        email_rcpt = str(settings.MAIL_DEPLOY_TO).split(';')

        to_email = []

        release_notes = []
        bggray = 'class="bg-gray"'

        # cc e-mails
        for email in emails_cc:
            to_email.append({'email': email, 'type': 'bcc'})

        # recipient e-mail
        for email in email_rcpt:
            to_email.append({'email': email, 'type': 'to'})

        # e-mails dos usuarios responsáveis pelas tarefas
        for issue in issues:

            asana_task = None
            asana_data = ''

            # if has asana id
            if hasattr(issue, 'AsanaID'):
                asana_task = self.asanaUtils.get_task(issue.AsanaID)

            if issue.Type in issue_types_deploy:

                # add asana data to release note
                if asana_task is not None:

                    asana_task_html = [
                        '<h4><a href="https://app.asana.com/0/%s/%s" target="_blank">[Asana Task] %s</a></h4>' % (str(asana_task['projects'][0]['id']), issue.AsanaID, asana_task['name']),
                        '<div>%s</div>' % asana_task['notes']
                    ]

                    asana_data = ''.join(d for d in asana_task_html)
                    self.asanaUtils.send_notification(issue.AsanaID)

                url = issue.youtrack.url + '/issue/' + issue.id

                issue_description = issue.description if hasattr(issue, 'description') else ''

                # add issue to release notes
                notes = [
                    '<li %s>' % bggray,
                    '<h3><a href="%s"><b># %s - %s</b></a></h3>' % (url, issue.id, issue.summary),
                    '<div>%s <br /> %s</div>' % (issue_description, asana_data),
                    '</li>'
                ]

                if bggray == '':
                    bggray = 'class="bg-gray"'
                else:
                    bggray = ''

                # adiciona ao release notes os dados da task
                release_notes.append(''.join(i for i in notes))

        release_notes = '<br />'.join(c for c in release_notes)

        # envia e-mail
        options = {
            'template_name': settings.MAIL_DEPLOY_MANDRILL_TEMPLATE,
            'template_content': [],
            'global_merge_vars': [
                {'name': 'release_tag', 'content': release_tag},
                {'name': 'release_notes', 'content': release_notes},
                {'name': 'repo_name', 'content': repo_name}
            ]
        }

        mail_sender = SendMail()
        mail_sender.send_mail(from_email, to_email, subject, '', options)

    @staticmethod
    def notify_to_verify(issues, release_tag, repo_name):
        to_email = []
        merge_vars = []
        user_tasks = {}

        if len(issues) == 0:
            return

        from_email = settings.MAIL_FROM_ADDRESS
        subject = settings.MAIL_VERIFY_SUBJECT
        subject = str(subject).replace('{{release_tag}}', release_tag)
        subject = str(subject).replace('{{repo_name}}', repo_name)
        emails_cc = str(settings.MAIL_VERIFY_CC).split(';')
        user = None

        # e-mails em cópia via configuração
        for email in emails_cc:
            to_email.append({'email': email, 'type': 'bcc'})

        # e-mails dos usuarios responsáveis pelas tarefas
        for issue in issues:
            user = YoutrackUtils.get_user(issue.Assignee)
            if user is not None:
                if len([str(c) for c in to_email if user.email in c.values()]) == 0:
                    to_email.append({'email': user.email, 'type': 'to'})
                if user.email not in user_tasks:
                    user_tasks[user.email] = {}
                    user_tasks[user.email]['tasks'] = []
                    user_tasks[user.email]['name'] = user.fullName
                url = issue.youtrack.url + '/issue/' + issue.id
                issue_link = '<a href="%s">%s</a>' % (url, issue.id)
                user_tasks[user.email]['tasks'].append(issue_link)

        # create merge vars for mandrill template with fields: user_name, tasks, release_tag
        for email, user_data in user_tasks.iteritems():

            myvars = [
                {'name': 'user_name', 'content': user_data['name']},
                {'name': 'tasks', 'content': '<br/>'.join(str(t) for t in user_data['tasks'])},
                {'name': 'release_tag', 'content': release_tag},
                {'name': 'repo_name', 'content': repo_name}
            ]

            merge_vars.append({
                'rcpt': email,
                'vars': myvars
            })

            # inject merge vars for the cc recipients
            for emailcc in emails_cc:
                merge_vars.append({
                    'rcpt': emailcc,
                    'vars': myvars
                })

        # envia e-mail
        options = {
            'template_name': settings.MAIL_VERIFY_MANDRILL_TEMPLATE,
            'template_content': [],
            'merge_vars': merge_vars
        }

        mail_sender = SendMail()
        return mail_sender.send_mail(from_email, to_email, subject, '', options)
