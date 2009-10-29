from django_assets.conf import settings


"""XXX

def setup_module():
    settings.MEDIA_ROOT = ..


def test_simple():
    make sure the output file doesn't exist

    b = Bundle('in1.css', 'in2.css', output='out.css')
    process(b)

    make sure the output file exists, and matches the expected one

    process(b)

    make sure the output timestamp hasn't changed (or that build wasn't called)"""