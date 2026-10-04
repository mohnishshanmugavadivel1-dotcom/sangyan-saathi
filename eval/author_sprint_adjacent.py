# -*- coding: utf-8 -*-
"""Authors eval/cases_sprint_adjacent.jsonl BEFORE any engine change in the Oct-4 sprint (rc2). Synthetic, author-written by the engine's author (NOT independent).
must: ESC = route must be ESCALATE; NOT_ESC = route must not be ESCALATE; STOP = urgent block must start with A_STOP_PAYMENT; TRADEOFF = reported, not scored as pass/fail.
group: TARGET = the 7 fresh-set cases the sprint targets (they are burned: post-hoc, not fresh); ADJ = adjacent cases written for this sprint; CTRL = controls for existing behaviour.
Hindi/Hinglish cases: NOT reviewed by a fluent speaker."""
import json, os
C = [
 ("T01","TARGET","X08 text","After I paid the registration amount, the advisor kept finding new charges: first insurance, then tax.","ESC","en"),
 ("T02","TARGET","X11 text","maine trader ko 50000 transfer kar diya, ab woh withdrawal ke liye aur paise maang raha hai","ESC","hinglish"),
 ("T03","TARGET","X13 text","Paid 15,000 to the account he gave me; now he wants more.","ESC","en"),
 ("T04","TARGET","X14 text","Transferred 25,000 as processing fee. They are asking for another 25,000.","ESC","en"),
 ("T05","TARGET","X15 text","Rs 4,000 was sent from my phone to an unknown number.","ESC","en"),
 ("T06","TARGET","X24 text","They gave me until tonight to pay 15,000 or lose the account; I am thinking of paying.","STOP","en"),
 ("T07","TARGET","X40 text","I entered my card number and CVV on a page that opened from the SMS.","ESC","en"),
 # subject-less completed payment + context
 ("A01","ADJ","subjectless+demand","Paid 20,000 to the number he sent; they are now asking for 10,000 more.","ESC","en"),
 ("A02","ADJ","subjectless+demand","Transferred 8,000 as clearance fee. The agent wants another 8,000.","ESC","en"),
 ("A03","ADJ","subjectless+unknown recipient","Sent Rs 12,000 to an unknown account from my UPI.","ESC","en"),
 ("A04","ADJ","subjectless+tax demand","Deposited 50,000 on the platform. Now they say tax of 15,000 must be paid before withdrawal.","ESC","en"),
 ("A05","ADJ","subjectless+kyc purpose","Remitted 30,000 for KYC update, now the caller demands 5,000 more.","ESC","en"),
 ("A06","ADJ","passive unfamiliar upi","Rs 7,500 was transferred from my account to an unfamiliar UPI ID.","ESC","en"),
 # subject-less benign
 ("B01","ADJ","benign subjectless","Paid Rs 799 to Netflix.","NOT_ESC","en"),
 ("B02","ADJ","benign subjectless","Paid 1,200 to Zomato via UPI.","NOT_ESC","en"),
 ("B03","ADJ","benign passive","Rs 450 was sent to Ramesh for the cab share.","NOT_ESC","en"),
 ("B04","ADJ","benign own account","Transferred 25,000 to my own savings account.","NOT_ESC","en"),
 ("B05","ADJ","benign + non-money ask","Paid the electricity bill of 1,850. They are asking for a rating.","NOT_ESC","en"),
 ("B06","ADJ","benign + receipt","Paid 3,000 rent to the landlord. He wants a receipt.","NOT_ESC","en"),
 ("B07","ADJ","benign + extra amount (known trade-off)","Paid 2,000 advance to the plumber; he asked for 300 more for parts.","TRADEOFF","en"),
 ("B08","ADJ","benign + extra amount (known trade-off)","Sent 5,000 to the caterer. The caterer is asking for another 1,000 on the day.","TRADEOFF","en"),
 # credential entry
 ("C01","ADJ","credential entry","I filled in my UPI PIN on the link the caller sent me.","ESC","en"),
 ("C02","ADJ","credential entry","I submitted my login details on the website they sent.","ESC","en"),
 ("C03","ADJ","credential entry","I clicked the link in the message and typed my card number and CVV.","ESC","en"),
 ("C04","ADJ","negated","I did not enter my CVV on the page they sent.","NOT_ESC","en"),
 ("C05","ADJ","hypothetical","If I entered my card number on that link, what should I do?","NOT_ESC","en"),
 ("C06","ADJ","advice/imperative","Never enter your card number on a page opened from an SMS.","NOT_ESC","en"),
 ("C07","ADJ","quoted request","The SMS said: enter your card number and CVV on this page.","NOT_ESC","en"),
 ("C08","ADJ","ordinary PIN","I entered my PIN at the ATM and withdrew cash.","NOT_ESC","en"),
 ("C09","ADJ","ordinary checkout","I entered my card number on the Amazon checkout page to buy a book.","NOT_ESC","en"),
 ("C10","ADJ","almost","I almost entered my CVV on the page they sent but closed it.","NOT_ESC","en"),
 ("C11","ADJ","future","I am going to enter my card details on the link they sent.","NOT_ESC","en"),
 ("C12","ADJ","refused","He asked me to enter my CVV on a page he sent; I refused.","NOT_ESC","en"),
 # Hinglish
 ("H01","ADJ","hinglish dative","maine agent ko 20000 transfer kar diya, ab woh aur paise maang raha hai","ESC","hinglish"),
 ("H02","ADJ","hinglish dative","maine broker ko 5000 bhej diye, ab woh tax ke liye aur paise maang rahe hain","ESC","hinglish"),
 ("H03","ADJ","hinglish benign","maine dukaan ko 500 pay kar diya","NOT_ESC","hinglish"),
 ("H04","ADJ","hinglish denial","maine trader ko paise nahi bheje, woh aur paise maang raha hai","NOT_ESC","hinglish"),
 ("H05","ADJ","hinglish third party paid me","usne mujhe 1000 transfer kar diya","NOT_ESC","hinglish"),
 # repeated charges
 ("R01","ADJ","repeated charges","After I paid the fee, the broker kept adding new charges every week.","ESC","en"),
 ("R02","ADJ","repeated charges","I paid the deposit; now the company keeps inventing extra fees.","ESC","en"),
 ("R03","ADJ","repeated charges, no iterative marker (stretch)","I paid the registration amount, then they added a GST charge, then a compliance charge.","ESC","en"),
 ("R04","ADJ","ordinary extra charge","I paid for my insurance premium and the insurer added GST as shown on the invoice.","NOT_ESC","en"),
 ("R05","ADJ","ordinary","I paid the hotel bill; they kept the extra charges off my invoice.","NOT_ESC","en"),
 ("R06","ADJ","denied + repeated demand","I did not pay the registration amount, the advisor keeps finding new charges.","NOT_ESC","en"),
 # pending
 ("P01","ADJ","pending deliberation","I am considering paying the 10,000 fee they asked for.","STOP","en"),
 ("P02","ADJ","pending deadline (stretch)","They gave me 48 hours to deposit 20,000 or the account closes.","STOP","en"),
 ("P03","ADJ","negated pending","I am not thinking of paying them anything.","NOT_ESC","en"),
 ("P04","ADJ","ordinary bill (known trade-off)","I am thinking of paying my electricity bill tonight.","TRADEOFF","en"),
 ("P05","ADJ","gave-me not a payment","They gave me a receipt for the 15,000 I paid last month.","NOT_ESC","en"),
 ("P06","ADJ","gave-me not a payment","The shopkeeper gave me until Friday to pick up the order.","NOT_ESC","en"),
 # controls
 ("K01","CTRL","explicit subject escalates","I paid 60,000 to the advisor and now he asks for taxes before release.","ESC","en"),
 ("K02","CTRL","explicit ordinary","I paid 1,200 to Zomato via UPI.","NOT_ESC","en"),
 ("K03","CTRL","bank notice","Rs 799 was debited from my account for my Netflix plan.","NOT_ESC","en"),
 ("K04","CTRL","attempt denied","I attempted to pay 3000 but did not complete it.","NOT_ESC","en"),
 ("K05","CTRL","third party paid","My brother paid 50,000 to the agent and now they want more.","NOT_ESC","en"),
 ("K06","CTRL","claim","The agent said I paid 5,000 last week but I never did.","NOT_ESC","en"),
 ("K07","CTRL","pending","I will send the clearance amount tonight.","STOP","en"),
]
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "cases_sprint_adjacent.jsonl"), "w", encoding="utf-8") as f:
    for i, g, why, t, must, lang in C:
        f.write(json.dumps({"id": i, "group": g, "why": why, "text": t, "situation": "NO_ACTION_YET", "must": must, "lang": lang, "lang_review": "NOT reviewed by a fluent speaker" if lang != "en" else "n/a", "synthetic": True, "author": "engine author (not independent)"}, ensure_ascii=False) + "\n")
print(len(C))
