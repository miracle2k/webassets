from fabric.api import run, put, env

env.hosts = ['elsdoerfer.com:2211']

def publish_docs():
    target = '/var/www/elsdoerfer/files/docs/webassets'
    run('rm -rf %s' % target)
    run('mkdir %s' % target)
    put('build/sphinx/html/*', '%s' % target)