import django.template

from blueware.hooks.framework_django import (
        blueware_browser_timing_header, blueware_browser_timing_footer)

register = django.template.Library()

register.simple_tag(blueware_browser_timing_header)
register.simple_tag(blueware_browser_timing_footer)
