## FORMAT
type - instrument - channel


## CREDIT
credit - bank_account - upi ✅
credit - bank_account - neft
credit - bank_account - rtgs
credit - bank_account - imps
credit - bank_account - cheque
credit - bank_account - cash          -> cash deposit at branch / CDM
credit - bank_account - atm           -> cash deposit via ATM

interest - bank_account - NULL        -> savings / FD interest credit

refund - bank_account - upi
refund - bank_account - debit_card
refund - credit_card - credit_card    -> merchant refund on credit card

reversal - credit_card - credit_card ✅
reversal - bank_account - bank_account
reversal - bank_account - debit_card
reversal - bank_account - upi
reversal - bank_account - atm         -> failed ATM withdrawal reversal


## DEBIT
debit - bank_account - upi ✅
debit - bank_account - debit_card ✅
debit - bank_account - neft
debit - bank_account - rtgs
debit - bank_account - imps
debit - bank_account - cheque
debit - bank_account - nach           -> NACH / ECS auto-debit (SIP, loan EMI, insurance)

debit - credit_card - credit_card ✅
debit - credit_card - upi ✅

auto payment - bank_account - debit_card ✅
auto payment - credit_card - credit_card ✅


## NEUTRAL
self - bank_account - NULL            -> self account movement (own A/C to own A/C)
self - wallet - upi                   -> loading own wallet from own bank account
self - bank_account - atm            -> ATM cash withdrawal
balance - bankaccount - NULL ✅