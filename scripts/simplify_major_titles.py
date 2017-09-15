from django_bootstrap import bootstrap
bootstrap()

from majors.models import Major

def main():
    count = 0
    for major in Major.objects.all():
        old_simplified_title = major.simplified_title
        major.simplified_title = Major.simplify_title(major.title)
        if old_simplified_title != major.simplified_title:
            count += 1
            major.save()
    print(count, 'changed')

if __name__ == '__main__':
    main()
    
