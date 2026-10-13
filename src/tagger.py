"""Rule-based review tagger for MoveInSync Play Store reviews (taxonomy v2).
Free, deterministic, no API needed. Multi-label: returns tag1, tag2, trigger, owner.
"""
import re

# ---- patterns (applied to lower-cased text) --------------------------------
P = {
 "RATEPROMPT": r"(rat(e|ing)|feedback|review)\b.{0,40}\b(every|each|always|force|forc|compuls|skip|again|popup|pop-up|pop up|annoy|irritat)|\b(every|each|always|force|forc|compuls|skip)\b.{0,40}\b(rat(e|ing)|feedback)\b|ask(s|ing)? (me )?(for )?(a )?(rating|feedback)|rating (should|shouldn)",
 "SESSION":    r"(too|so) many otp|this much otp|otp.{0,20}(again and again|every ?time|everytime|so often|frequent)|log(ged|ging|s)? ?(me )?(out|off)|logout|log ?off|sign(ed|ing)? out|re-?log ?in|login again|log in again|logging in again|(again and again|every ?time|everytime|frequent(ly)?|repeated(ly)?|daily|every day|each time)\W.{0,30}(log ?in|login|authenticat|credential|verify|otp)|(log ?in|login|authenticat|credential|verif\w*)\W.{0,30}(again and again|every ?time|everytime|frequent(ly)?|repeated(ly)?|daily|every day|each time)|session (expire|time|out)|losing? (my )?(login|credential)|loosing login|asks? (for )?(credential|password|login)",
 "OTP":        r"(view|show|see|share|give|boarding|trip|ride|cab|driver|pickup|pick-up|pick up).{0,25}\botp\b|\botp\b.{0,25}(driver|boarding|pickup|pick-up|pick up|seat ?belt|cab|trip|ride)|seat ?belt",
 "LOGIN":      r"log ?in|login|sign ?in|sign ?up|register again|not registered|registration (failed|issue|problem)|verif\\w*|validat\\w* (my )?(identity|account)|authenticat|\botp\b|passcode|password|credential|(can.?t|cannot|unable to|not able to) (access|log)|activation|identity",
 "BOOKING":    r"\bbook(ing|ed|s)?\b|roster|schedul(e|ing|ed)|cancel(l)?(ed|ing|ation)?|wait ?list|no[ -]?show|\bslot|\bseat\b|\bdesk\b|shift|\bplan\b|trip (not )?(created|created|showing|visible|listed)|check[- ]?in|adhoc|ad-hoc|modify",
 "ROUTING":    r"\broute|routing|\broot\b|pooling|\bpool\b|pick(-| )?up (point|location|spot|sequence|order)|pickup (point|location|spot|sequence|order)|sequence|detour|longer (way|route)|clubb|shared? cab|cab sharing|co-?passenger|unnecessary (stop|detour)|\bstops?\b|dedup|same (place|spot|location).{0,30}(time|different)",
 "ETA":        r"\beta\b|\bgps\b|track(ing|er|s)?\b|live (location|status|track)|real[- ]?time|\bmap\b|navigation|(cab|vehicle|driver|bus|taxi) (location|position)|location (is|was|not|wrong|inaccura|update|accura|shows?|refresh|fluctuat|jump|incorrect)|(wrong|incorrect|inaccurate) (location|time|eta)|drop (time|timing)|arrival time|(pickup|pick up|pick-up) time (is|was|shown|showing|wrong)|distance|\bkm\b|zoom",
 "LATE":       r"\blate\b|delay|(no|not)[ -]?show|did ?n.?t (come|arrive|turn|show|pick)|never (came|arrived|show|picked)|not (come|arrive|arrived|picked|pick|reach|turn)|waiting|\bwait(ed|s)?\b|\bdriver|\bdrivers\b|cab (is|was|are|were|came|arrived|service|facility|driver|quality)|vehicle (is|was|came|quality|condition)|rude|behaviou?r|misbehav|rash|\bac\b|air condition|dirty|unprofessional|cab services?|cabs? (cancel|not)|transport(ation)? (service|facility|is|was)|\bcab\b.{0,30}(not|never|late|cancel)|pickup (was|is) late",
 "SUPPORT":    r"support|help ?desk|helpdesk|help line|helpline|customer (care|service|support)|complain|escalat|ticket|no (response|reply|one (responds|replies|answers|picks))|not (respond|reply|answer|pick)|transport (team|desk|manager|admin|department)|facility team|call(s|ed|ing)? (not|never|is not)|unreachable|not reachable|resolv(e|ed|ing|ution)|grievance|raised (a )?(complaint|issue|concern)",
 "NOTIF":      r"notif|alert|\bsms\b|text message|push (message|msg)|reminder|pop ?-?up|\bping|message (not|never|is not)|no message|messages? (come|came|arrive)",
 "REQUEST":    r"please (add|provide|include|bring|give|allow|enable|introduce)|(should|must|need to|needs to|can you|could you|kindly|pls|plz) (add|provide|include|bring|give|allow|have|enable|introduce|be able)|\bwish\b|suggest(ion)?|would be (nice|great|better|helpful|good)|it would help|option (to|for)|add (a |an |the )?(option|feature|button|filter|dark|monthly|search|chat|call)|feature (request|to|for)|\bdark (mode|theme)|no (chat|call) (option|feature)|no (option|feature|way) (to|for)|there is no (option|way|feature)|there.?s no (option|way|feature)|doesn.?t (have|allow|provide|let) (an |the )?(option|feature)|not (compatible|supported) (with|on)|support for",
 "UI":         r"\bui\b|\bux\b|interface|design|layout|redesign|new (look|version|update|ui|design|feature)|old (version|ui|design|look)|font|colou?r|confus|complicat|user[- ]?friendly|easy to (use|navigate)|difficult to (use|navigate)|navigation (is|was)|clutter|cluttered|too many (steps|clicks|screens|taps)|extra (step|click)|unnecessary (step|click|screen|prompt|agreement)|agreement|zoom|scroll|screen (size|rotation)|tablet|button|icon|menu",
 "CRASH":      r"crash|not (opening|open|working|loading|responding|launching|start)|(does ?n.?t|doesn.?t|do ?n.?t|won.?t|will not|wont|can.?t|cannot|unable to|never) (open|work|load|launch|start|run|function|respond)|loading|\bload\b|stuck|\bhang|freez|\bslow|\blag|\bbug|glitch|error|something went wrong|oops|blank|white screen|black screen|server|uninstall|reinstall|re-install|force (close|stop)|keeps? (closing|stopping|crash)|\bnot responding|doesn.?t respond|useless app|app (is|was) (not|dead|down)|performance|\bhangs?\b|unresponsive|timeout|time out|time-out|network|internet|connection|disconnect|flashlight|camera|\bqr\b|scan|update(d|s)?\b.{0,30}(not|issue|problem|crash|error|worse)",
 "SAFETY":     r"\bsafe(ty)?\b|unsafe|women|woman|\bnight\b|harass|\bsos\b|panic|security|escort|molest|accident",
}
UNCLEAR_RE = r"^[\W_\d]*(worst|bad|very bad|poor|very poor|good|nice|ok|okay|useless|pathetic|waste|nonsense|bekar|bakwas|rubbish|horrible|terrible|awful|disgusting|pathetic|not good|average|3 star|1 star|0 star|hate|garbage|trash|zero|lazy|shit\w*|crap|worst app|bad app|waste app|useless app|worst app ever|poor app|very poor app)[\W_]*(app|application|ever|experience|service|one|\w{0,12})?[\W_]*$"

PRIORITY = ["RATEPROMPT","SESSION","OTP","SUPPORT","LOGIN","NOTIF","ETA","CRASH","LATE","BOOKING","ROUTING","REQUEST","UI","SAFETY"]
RX = {k: re.compile(v, re.I) for k, v in P.items()}
UNCLEAR = re.compile(UNCLEAR_RE, re.I)
UPDATE = re.compile(r"updat|upgrad|new version|latest version|new release|new feature|since (the )?(last|new|latest)", re.I)

OWNER = {"CRASH":"Eng","LOGIN":"Eng","SESSION":"Eng","ETA":"Eng","BOOKING":"Eng","ROUTING":"Eng","OTP":"Product",
         "NOTIF":"Eng","UI":"Product","RATEPROMPT":"Product","REQUEST":"Product","LATE":"Ops","SUPPORT":"Ops",
         "SAFETY":"Ops","OTHER":"Unclear","UNCLEAR":"Unclear"}
TRIG = {"LOGIN":"at_login","SESSION":"at_login","BOOKING":"at_booking","ETA":"during_trip","LATE":"during_pickup",
        "RATEPROMPT":"after_ride","ROUTING":"none","CRASH":"none","OTP":"during_pickup","NOTIF":"none","SUPPORT":"none",
        "REQUEST":"none","UI":"none","SAFETY":"none","OTHER":"none","UNCLEAR":"none"}

COMPETITORS = re.compile(r"routematic|route ?mate|routemate|ola|uber|quick ?ride|safetrax|pickme|rapido", re.I)

def tag_text(text):
    t = (text or "").strip()
    low = COMPETITORS.sub(" competitor ", t.lower())
    if len(re.sub(r"[\W_]+", "", low)) < 4 or UNCLEAR.match(low):
        return "UNCLEAR", None, "none", "Unclear"
    hits = [k for k in PRIORITY if RX[k].search(low)]
    # CRASH only if no feature-specific complaint matched (global failure), unless it is the only/first hit
    if not hits:
        vague = re.search(r"worst|bad|poor|useless|pathetic|waste|rubbish|horrible|terrible|awful|disgust|hate|garbage|bekar|bakwas|nonsense|disappoint", low)
        return ("UNCLEAR" if (len(low) < 40 or vague) else "OTHER"), None, "none", "Unclear"
    # resolve conflicts
    if "OTP" in hits and "LOGIN" in hits and not re.search(r"log ?in|login|regist|verif", low):
        hits.remove("LOGIN")
    TOP = ("RATEPROMPT", "SESSION", "OTP")
    top = [h for h in hits if h in TOP]
    if top:
        ordered = top + [h for h in hits if h not in top]
    else:
        pos = {h: (RX[h].search(low).start() if RX[h].search(low) else 0) for h in hits}
        ordered = sorted(hits, key=lambda h: (pos[h], PRIORITY.index(h)))
    tag1 = ordered[0]
    tag2 = ordered[1] if len(ordered) > 1 else None
    trig = "after_update" if UPDATE.search(low) else TRIG[tag1]
    if tag1 == "CRASH" and re.search(r"not (opening|open)|won.?t open|doesn.?t open|launch|stuck on (splash|loading)|open the app", low) and trig == "none":
        trig = "at_launch"
    return tag1, tag2, trig, OWNER[tag1]
