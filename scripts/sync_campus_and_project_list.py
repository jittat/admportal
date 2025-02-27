from django_bootstrap import bootstrap
bootstrap()

from criteria.views import update_campus_keys, update_project_list

def main():
    update_campus_keys()
    update_project_list()


if __name__ == '__main__':
    main()
