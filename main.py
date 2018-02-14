#!/usr/bin/env python3

import io, urllib.request, PIL.Image, PIL.ImageTk, re, pickle
from tkinter.filedialog import askopenfile, asksaveasfile
from tkinter.simpledialog import askstring
from tkinter.messagebox import showerror,  askokcancel
from tkinter import tix
import mtgsdk

LANG = "French"
CARD_BOTTOM = "http://upload.wikimedia.org/wikipedia/en/a/aa/Magic_the_gathering-card_back.jpg"
CARD_DIM = (223,310)

def list_sets():
        sets = mtgsdk.Set.all()
        vals = [(s.name, s.code) for s in sorted(sets, key=lambda x:x.release_date, reverse=True)
        ]
        return vals


class Card(mtgsdk.Card) :

        def __new__(cls, response_dict=dict()) :
                if "amount" not in response_dict.keys():
                        response_dict["amount"] = 1
                obj = object.__new__(Card)
                obj.__dict__ = response_dict
                return obj

        @staticmethod
        def find(id):
                return mtgsdk.QueryBuilder(Card).find(id)

        @staticmethod
        def where(**kwargs):
                return mtgsdk.QueryBuilder(Card).where(**kwargs)

        @staticmethod
        def all():
                return mtgsdk.QueryBuilder(Card).all()

        def __eq__(self, other):
                return self.__dict__ == other.__dict__

        def __iadd__(self, amount):
                """Shortcut for self.amount += xxx"""
                self.amount += amount
                return self

        def __isub__(self, amount):
                """See __iadd__"""
                self.amount -= amount
                return self

        def __getstate__(self):
                return self.__dict__

        def __setstate__(self, state):
                self.__dict__ = state

        def get_foreign_name(card) :
                """Returns, if present, the name of the card in language LANG.
                Else, returns card.name (usually in English)"""
                if hasattr(card, "names") :
                        if card.number.endswith("a"):
                                number = card.number[:-1]+"b"
                                card2 = Card.where(set=card.set, number=number).all()[0]
                                return card._get_foreign_name() + " // " + card2._get_foreign_name()
                        else :
                                number = card.number[:-1]+"a"
                                card2 = Card.where(set=card.set, number=number).all()[0]
                                return card2._get_foreign_name() + " // " + card._get_foreign_name()

        def _get_foreign_name(card):
                if card.foreign_names is None :
                        return card.name
                for d in card.foreign_names :
                        if d["language"] == LANG :
                                return d["name"]
                return card.name

        def getimg(card):
                """Retrives and returns the picture of the card
                if possible, in the global LANG language"""
                if card.image_url is None :
                        url = CARD_BOTTOM
                elif card.foreign_names is None :
                        url = card.image_url
                else :
                        url = None
                        for l in card.foreign_names :
                                if l["language"] == LANG :
                                        url = l.get("imageUrl", CARD_BOTTOM)
                                        break
                        if url is None :
                                url = card.image_url
                data = io.BytesIO(urllib.request.urlopen(url).read())
                img = PIL.Image.open(data)
                img = img.resize(CARD_DIM)
                return PIL.ImageTk.PhotoImage(img)


class CardPresenter :

        def __init__(self, master=None, cards=list()):
                if master is None :
                        master = tix.Tk()

                self.main = tix.Frame(master)
                self.main.config(width=480, height=600)
                # width is the minimun correct, while height can change from 310+height(button) to +inf

                # left part : list of all the cards
                self.names = tix.ScrolledListBox(self.main)
                self.names.listbox.configure(width=30, bg="#ffffff")

                self.update(cards)

                # right part : single-card details and picture
                self.imglbl = tix.Label(self.main)
                self.selection_reset()

                # bottom : add-a-card Button
                self.addacard = tix.Button(self.main, text=" + ", command=self.search)

                # bottom : set codes index
                self.askcode =  tix.Button(self.main, text=" ? ", command=self.showsets)
                self.set_codes = None

                self.main.bind_all("<Control-s>", self.save)
                self.main.bind_all("<Control-o>", self.load)
                self.names.listbox.bind_all("<<ListboxSelect>>", self.display_card)
                self.main.bind_all("<KP_Add>", self.inc) # "+" from the numeric pad
                self.main.bind_all("<plus>", self.inc) # "+" from the alphabetic pad
                self.main.bind_all("<KP_Subtract>", self.dec) # idem
                self.main.bind_all("<minus>", self.dec)

                self.main.pack(fill="both",expand=True)
                self.names.place(x=0, y=0, anchor="nw", relheight=1.0)
                self.imglbl.place(anchor="ne", relx=1.0, rely=0.0, width=CARD_DIM[0], height=CARD_DIM[1])
                self.addacard.place(anchor="se", relx=1.0, rely=1.0)
                self.askcode.place(anchor="se", relx=0.9, rely=1.0)

        def save(self, dummy_arg=None):
                # We should also find a way to store the pictures
                file = asksaveasfile(mode="wb")
                if file is None :
                        return
                pickle.dump(self.cards, file, protocol=4)

        def load(self, dummy_arg=None):
                file = askopenfile(mode="rb")
                if file is None :
                        return
                self.update(pickle.load(file))

        def update(self, cards=None):
                self.selection_reset()
                if cards is not None :
                        self.cards = cards
                        self.cards.sort(key=lambda card:card.get_foreign_name())
                self.names.listbox.delete(0,"end")
                self.names.listbox.insert(0,
                *[card.get_foreign_name()+" (x{})".format(card.amount)*bool(card.amount-1) for card in self.cards])

        def update_one(self, index):
                self.names.listbox.delete(index)
                self.names.listbox.insert(index, self.cards[index].get_foreign_name()+" (x{})".format(self.cards[index].amount)*bool(self.cards[index].amount-1))

        def selection_reset(self):
                self.curimg = None
                self.curindex = None

        def display_card(self, dummy_arg=None):
                index = self.names.listbox.curselection()
                if not index : return # if no selection
                index = index[0]
                if self.curindex != index :
                        card = self.cards[index]
                        self.curimg = card.getimg()
                        self.imglbl.configure(image=self.curimg)
                        self.curindex = index

        def search(self,initial=str()):
                # 1. Ask the card ID (set + number)
                resp = askstring("Ajouter une carte", "Saisissez l'identifiant à 6~8 caractères en bas à gauche de la carte", initialvalue=initial)
                if resp is None :
                        return
                z = re.fullmatch("(?P<code>p?[A-Za-z][A-Za-z0-9]{2})(?P<number>[0-9]{1,3}(a|b)?)", resp)
                if not z :
                        showerror("Saisie incorrecte", "Assurez-vous d'avoir correctement saisi l'identifiant (en respectant la casse)")
                        return
                set_id, num = z.groupdict()["code"].upper(), z.groupdict()["number"].lstrip("0")

                # 2. Proceed the request
                rq = Card.where(language=LANG, set=set_id, number=num).all()
                if not len(rq) :
                        rq = Card.where(language=LANG, set=set_id, number=num+"a").all() # maybe it's a flip card
                        if not len(rq) :
                                showerror("Aucune carte trouvée", "Le service distant ne répond pas, ou vérifiez votre saisie")
                                return
                if len(rq) > 1 : # never happens yet
                        tl = tix.TopLevel(self)
                        lf = tix.LabelFrame(tl, text="Carte(s) trouvée(s), cliquez sur la bonne")
                        lf.pack(fill="both",expand=True)
                        for i,card in enumerate(rq):
                                def mkbuttonjob(tl, rq, card):
                                        def buttonjob():
                                                tl.destroy()
                                                rq.clear()
                                                rq.append(card)
                                        return buttonjob
                                tix.Button(lf, image=card.getimg(), command=mkbuttonjob(tl, rq, card)).grod(column=i)
                        tl.mainloop()

                rq = rq[0]
                # 3. Add the found card to the existing database
                if rq in self.cards :
                        index = self.cards.index(rq)
                        self.cards[index] += 1
                        self.update_one(index)
                else :
                        self.cards.append(rq)
                        self.update(self.cards) # we pass self.cards for parameter, so that update will sort it
                        self.selection_reset()

        def _select_update(f):
                def f_(self, dummy_arg=None):
                        index = self.names.listbox.curselection()
                        if not index : return
                        card = self.cards[index[0]]

                        if f(self, card) is None : # if f returns something if we don't have to update the selection
                                self.names.listbox.delete(index)
                                self.names.listbox.insert(index, card.get_foreign_name()+" (x{})".format(card.amount)*bool(card.amount-1))

                                self.names.listbox.selection_clear(index)
                                self.names.listbox.selection_set(index)
                return f_

        @_select_update
        def inc(self, card):
                """Increases the selected card's amount by 1"""
                card += 1

        @_select_update
        def dec(self, card):
                """Decreases the selected card's amount by 1,
                and removes it (after confirm) if it reaches 0"""
                if card.amount == 1 :
                        if askokcancel("Confirmation de suppression","Supprimer cette carte de l'inventaire ?") :
                                index = self.cards.index(card)
                                del self.cards[index]
                                self.names.listbox.delete(index)
                                self.selection_reset()
                        return -1
                else :
                        card -= 1

        def showsets(self):
                if self.set_codes is None :
                        self.set_codes = list_sets()
                tl = tix.Toplevel(self.main.master)
                lb = tix.ScrolledListBox(tl)
                lb.listbox.insert(0, *[x[0] for x in self.set_codes])
                lb.listbox.configure(width=30, height=30, bg="#ffffff")
                tl.bind("<Escape>", tl.destroy)
                def finish(event):
                        index = lb.listbox.curselection()
                        if not len(index) :
                                return
                        self.search(self.set_codes[index[0]][1])
                        tl.destroy()
                lb.listbox.bind("<<ListboxSelect>>", finish)
                lb.pack(fill="both",expand=True)


if __name__ == '__main__':
        cp = CardPresenter()
        cp.main.mainloop()
