# -*- coding: utf-8 -*-
"""Phase 5 fresh regression set (45 cases), written by the engine's author AFTER the Phase 4 repairs and BEFORE the Phase 5 fixes, and frozen (sha256 recorded) before any run.
Not independent: same author as the engine and as the earlier sets. They were written to cover the Phase 5 brief categories with new wording, not to match the planned fixes.
Hindi/Hinglish cases: language-review status UNREVIEWED by a fluent speaker. Schema = eval/cases_incident_state.jsonl."""
import hashlib, json, os, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "cases_final_fresh.jsonl"); FV = os.path.join(HERE, "..", "results", "final_verification")
E_, A_, N_, P_ = "ESCALATE", "ASK", "NORMAL", "PENDING"
UP, US, UC, UU, UD, UT, UCL, UN = "USER_PAID", "USER_SHARED_CREDENTIAL", "USER_PAYMENT_PENDING", "PAYMENT_UNCLEAR", "USER_DENIES", "THIRD_PARTY_PAID", "SENDER_CLAIMS_PAYMENT", "NO_INCIDENT"
# (id, cat, text, lang, ideal, ok, state, actor, sev, unc, ambiguous, urgent_first, why)
C = [
 ("X01", "unauthorised_debit", "There is a 12,500 debit in my savings account that I never made, the SMS shows an unknown UPI ID.", "en", E_, [E_, A_], UU, "UNKNOWN", "critical", True, False, None, "unexplained debit from the user's own account: contact bank and 1930 promptly; the user did not pay"),
 ("X02", "unauthorised_debit", "Money left my account this morning and I don't recognise the receiver.", "en", E_, [E_, A_], UU, "UNKNOWN", "critical", True, False, None, "unexplained debit"),
 ("X03", "unauthorised_debit", "Rs 8,000 got deducted from my card at a store I have never visited.", "en", E_, [E_, A_], UU, "UNKNOWN", "critical", True, False, None, "unexplained card debit"),
 ("X04", "unauthorised_debit", "I sent 5,000 to a number I don't recognise by mistake.", "en", E_, [E_, A_], UP, "USER", "high", False, False, None, "mistaken transfer to an unknown recipient: bank promptly"),
 ("X05", "unauthorised_debit", "My account shows a transfer of 30,000 to someone called Vikas, I do not know any Vikas.", "en", E_, [E_, A_], UU, "UNKNOWN", "critical", True, False, None, "unknown recipient"),
 ("X06", "unauthorised_debit", "मेरे खाते से 15,000 रुपये कट गए, मैंने कोई भुगतान नहीं किया", "hi", E_, [E_, A_], UU, "UNKNOWN", "critical", True, False, None, "Hindi: unexplained debit; the sentence contains a denial of paying"),
 ("X07", "completed_with_demand", "I deposited 90,000 in the crypto portal last week. Now support says a 10% clearance fee is needed before I can withdraw.", "en", E_, [E_], UP, "USER", "critical", False, False, None, "completed deposit + demand"),
 ("X08", "completed_with_demand", "After I paid the registration amount, the advisor kept finding new charges: first insurance, then tax.", "en", E_, [E_], UP, "USER", "critical", False, False, None, "completed + demands"),
 ("X09", "completed_with_demand", "I cleared the courier penalty of 3,500 and now a second agent says there is a pending duty.", "en", E_, [E_, A_], UP, "USER", "high", False, False, None, "completed + new demand"),
 ("X10", "completed_with_demand", "I made the first payment as the matrimonial contact asked and she is now pushing for a bigger transfer for customs.", "en", E_, [E_, A_], UP, "USER", "high", False, False, None, "completed + escalating demand"),
 ("X11", "completed_with_demand", "maine trader ko 50000 transfer kar diya, ab woh withdrawal ke liye aur paise maang raha hai", "hinglish", E_, [E_, A_], UP, "USER", "critical", False, False, None, "Hinglish completed + demand"),
 ("X12", "completed_with_demand", "मैंने ऐप में 40,000 रुपये जमा कर दिए थे, अब निकासी के लिए वे टैक्स माँग रहे हैं", "hi", E_, [E_, A_], UP, "USER", "critical", False, False, None, "Hindi completed + demand"),
 ("X13", "passive_subjectless", "Paid 15,000 to the account he gave me; now he wants more.", "en", E_, [E_, A_], UP, "USER", "high", False, False, None, "subject-less report: known design limit of the reader"),
 ("X14", "passive_subjectless", "Transferred 25,000 as processing fee. They are asking for another 25,000.", "en", E_, [E_, A_], UP, "USER", "high", False, False, None, "subject-less report: known design limit"),
 ("X15", "passive_subjectless", "Rs 4,000 was sent from my phone to an unknown number.", "en", E_, [E_, A_], UU, "UNKNOWN", "high", True, True, None, "passive; could be an unauthorised or a mistaken payment"),
 ("X16", "passive_subjectless", "The amount has been paid.", "en", N_, [N_, A_], UN, "UNKNOWN", "low", False, True, None, "no context at all: either answer is defensible"),
 ("X17", "passive_subjectless", "Rs 1,200 paid to Zomato via UPI", "en", N_, [N_, A_], UN, "UNKNOWN", "low", False, False, None, "bank-notice style legitimate payment"),
 ("X18", "denied_refused_failed", "I declined to pay the fee they demanded.", "en", N_, [N_, P_], UD, "USER", "low", False, False, None, "refusal"),
 ("X19", "denied_refused_failed", "I did not send them anything, I only replied once.", "en", N_, [N_], UD, "USER", "low", False, False, None, "denial"),
 ("X20", "denied_refused_failed", "I tried to pay 7,000 but the app showed the transaction failed.", "en", A_, [A_, N_], UU, "USER", "medium", True, True, None, "failed attempt: ask the user to confirm in the bank history"),
 ("X21", "denied_refused_failed", "The payment of 10,000 was reversed by my bank the same day.", "en", N_, [N_, A_], UN, "UNKNOWN", "low", False, True, None, "reversed by the bank"),
 ("X22", "denied_refused_failed", "I paid 6,000 yesterday, then the recipient sent it back to my account.", "en", A_, [A_, E_, N_], UU, "USER", "medium", True, True, None, "paid then returned: contradictory/unclear status"),
 ("X23", "pending", "I will transfer 20,000 after lunch to the person who messaged me about the offer.", "en", P_, [P_, A_], UC, "USER", "high", False, False, "A_STOP_PAYMENT", "pending to an unsolicited contact: stop-payment first"),
 ("X24", "pending", "They gave me until tonight to pay 15,000 or lose the account; I am thinking of paying.", "en", P_, [P_, A_], UC, "USER", "high", False, False, "A_STOP_PAYMENT", "pending under pressure"),
 ("X25", "pending", "Main abhi 30000 bhejne wala hoon, unhone kaha ki aaj hi karna hoga", "hinglish", P_, [P_, A_], UC, "USER", "high", False, False, "A_STOP_PAYMENT", "Hinglish pending under pressure"),
 ("X26", "denied_refused_failed", "मैंने उन्हें कोई पैसे नहीं भेजे", "hi", N_, [N_], UD, "USER", "low", False, False, None, "Hindi denial"),
 ("X27", "third_party_or_claim", "My uncle transferred 1 lakh to a stranger who promised double returns.", "en", A_, [A_, N_], UT, "THIRD", "medium", False, False, None, "third-party payment to a stranger: not the user's payment"),
 ("X28", "third_party_or_claim", "The message says I have already paid the customs fee, but I haven't.", "en", N_, [N_], UD, "CLAIM", "low", False, False, None, "sender claim + denial"),
 ("X29", "third_party_or_claim", "The website states that my order was paid for.", "en", N_, [N_, A_], UCL, "CLAIM", "low", False, False, None, "claim by a website"),
 ("X30", "third_party_or_claim", "My daughter paid the tuition through the college portal.", "en", N_, [N_], UT, "THIRD", "low", False, False, None, "third party, legitimate"),
 ("X31", "third_party_or_claim", "Unhone bola ki maine paise bhej diye, lekin maine kuch nahi bheja", "hinglish", N_, [N_], UD, "CLAIM", "low", False, False, None, "Hinglish claim + denial"),
 ("X32", "legit_everyday", "I bought 10 shares of Infosys through my broker app today.", "en", N_, [N_, A_], UN, "USER", "low", False, False, None, "ordinary investment transaction"),
 ("X33", "legit_everyday", "I started a SIP of 5,000 in an index fund yesterday.", "en", N_, [N_, A_], UN, "USER", "low", False, False, None, "ordinary investment"),
 ("X34", "legit_everyday", "I paid my credit card bill of 14,300 this morning.", "en", N_, [N_, A_], UP, "USER", "low", False, False, None, "ordinary bill"),
 ("X35", "legit_everyday", "I topped up my metro card with 500 rupees.", "en", N_, [N_, A_], UP, "USER", "low", False, False, None, "ordinary"),
 ("X36", "legit_everyday", "I transferred 20,000 to my own savings account in another bank.", "en", N_, [N_, A_], UP, "USER", "low", False, False, None, "own-account transfer"),
 ("X37", "legit_everyday", "मैंने बिजली का बिल भर दिया", "hi", N_, [N_, A_], UP, "USER", "low", False, False, None, "Hindi ordinary bill"),
 ("X38", "credential", "I typed my UPI PIN on the link the caller messaged me.", "en", E_, [E_, A_], US, "USER", "critical", False, False, None, "credential entered on a page the other side sent"),
 ("X39", "credential", "I gave the delivery guy the OTP over the phone.", "en", E_, [E_], US, "USER", "critical", False, False, None, "OTP shared"),
 ("X40", "credential", "I entered my card number and CVV on a page that opened from the SMS.", "en", E_, [E_, A_], US, "USER", "critical", False, False, None, "card details entered on a linked page"),
 ("X41", "credential", "The caller wanted my OTP but I refused and hung up.", "en", N_, [N_], UD, "USER", "low", False, False, None, "refusal"),
 ("X42", "credential", "maine unko apna OTP bata diya", "hinglish", E_, [E_], US, "USER", "critical", False, False, None, "Hinglish OTP shared"),
 ("X43", "credential", "I never share my PIN with anyone.", "en", N_, [N_], UN, "USER", "low", False, False, None, "general statement, not an incident"),
 ("X44", "contradictory", "I paid on Monday, no wait, I think I only started the payment and then cancelled. Not sure.", "en", A_, [A_], UU, "USER", "medium", True, False, None, "self-contradiction and explicit uncertainty"),
 ("X45", "contradictory", "I paid 5,000 and also shared my OTP with the caller.", "en", E_, [E_], US, "USER", "critical", False, False, None, "payment and credential share together"),
]
def main():
    with open(OUT, "w", encoding="utf-8") as f:
        for (i, cat, text, lang, ideal, ok, st, actor, sev, unc, amb, uf, why) in C:
            f.write(json.dumps({"id": i, "cat": cat, "sit": "NO_ACTION_YET", "text": text, "lang": lang, "ideal": ideal, "ok": ok, "state": st, "also": [], "actor": actor, "urgent_first": uf, "unc": unc, "sev": sev, "ambiguous": amb, "why": why,
                                "lang_review": "English only; written by the engine's author" if lang == "en" else "NOT reviewed by a fluent speaker (author-written)"}, ensure_ascii=False) + "\n")
    os.makedirs(FV, exist_ok=True); shutil.copyfile(OUT, os.path.join(FV, "fresh_cases.jsonl"))
    h = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    json.dump({"cases": len(C), "sha256": h, "frozen_before_phase5_fixes": True, "note": "authored before any Phase 5 engine change; never run before the final run"}, open(os.path.join(FV, "FRESH_FREEZE.json"), "w"), indent=1)
    print(len(C), h)
main()
