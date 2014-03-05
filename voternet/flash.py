"""Utility to display flash messages.

To add a flash message:

    add_flash_message('info', 'Login successful!')

To display flash messages in a template:
    
    $ for flash in get_flashed_messages():
        <div class="$flash.type">$flash.message</div>

Note: This should be added with web.py or become an independent module.
"""

import json
import web

def get_flashed_messages():
    flash = web.ctx.get('flash', [])
    web.ctx.flash = []
    return flash

def add_flash_message(type, message):
    flash = web.ctx.setdefault('flash', [])
    flash.append(web.storage(type=type, message=message))
    
def flash_processor(handler):
    flash = web.cookies(flash="[]").flash
    try:
        flash = [web.storage(d) for d in json.loads(flash) if isinstance(d, dict) and 'type' in d and 'message' in d]
    except ValueError:
        flash = []
    
    web.ctx.flash = list(flash)
    
    try:
        return handler()
    finally:
        # Flash changed. Need to save it.
        if flash != web.ctx.flash:
            if web.ctx.flash:
                web.setcookie('flash', json.dumps(web.ctx.flash))
            else:
                web.setcookie('flash', '', expires=-1)
