"""Mutation checks: break the UI in one specific way and confirm the web tests notice. Run: python3 -B tests/mutation_checks.py <drop_step|mute_reminder|reassure|hide_limits|alert_last> from rc/."""
import sys, unittest, io
sys.path.insert(0,'.'); sys.path.insert(0,'tests')
import tests.test_web as T
from saathi_rc.web import views
which=sys.argv[1]
if which=="drop_step":
    o=views._steps_html; views._steps_html=lambda st,l,c=None:o(st[1:],l,c)
elif which=="mute_reminder":
    o=views.registry_card_html
    views.registry_card_html=lambda r,l,demo=False:o(r,l,demo).replace("<div class='box concern' role='note'><p><strong>","<p class='muted'><strong>").replace("</p></div><p class='muted'>Source","</p><p class='muted'>Source")
elif which=="reassure":
    o=views.render_result
    views.render_result=lambda res,extra_registry=None,text="":o(res,extra_registry,text).replace(b"</main>",b"<p>This message looks safe.</p></main>")
elif which=="hide_limits":
    o=views.render_result
    import re
    views.render_result=lambda res,extra_registry=None,text="":re.sub(rb"<section class='box info' aria-labelledby='lh'>.*?</section>",b"",o(res,extra_registry,text),flags=re.S)
elif which=="alert_last":
    o=views.render_result
    views.render_result=lambda res,extra_registry=None,text="":o(res,extra_registry,text).replace(b"role='alert'",b"role='note'")
s=unittest.TestLoader().loadTestsFromModule(T); r=unittest.TextTestRunner(stream=io.StringIO()).run(s)
print(which,"-> failures caught:",len(r.failures)+len(r.errors))
