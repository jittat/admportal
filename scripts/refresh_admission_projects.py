from django_bootstrap import bootstrap
bootstrap()

from majors.models import AdmissionProject

def main():
    count = 0
    for project in AdmissionProject.objects.all():
        project.save()
        count += 1
    print(count, 'changed')

if __name__ == '__main__':
    main()
    
