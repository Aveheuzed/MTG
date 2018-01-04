#!/usr/bin/env python3

import io, urllib.request, PIL.Image, PIL.ImageTk, re, pickle
from tkinter.filedialog import askopenfile, asksaveasfile
from tkinter.simpledialog import askstring
from tkinter.messagebox import showerror,  askokcancel
from tkinter import tix
import mtgsdk

LANG = "French"

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

        def get_foreign_name(card) :
                """Returns, if present, the name of the card in language LANG.
                Else, returns card.name (usually in English)"""
                if card.foreign_names is None :
                        return card.name
                for d in card.foreign_names :
                        if d["language"] == LANG :
                                return d["name"]
                return card.name

        def getimg(card):
                """Retrives and returns the picture of the card
                if possible, in the global LANG language"""
                if card.foreign_names is None :
                        url = card.image_url
                else :
                        url = None
                        for l in card.foreign_names :
                                if l["language"] == LANG :
                                        url = l["imageUrl"]
                                        break
                        if url is None :
                                url = card.image_url
                data = io.BytesIO(urllib.request.urlopen(url).read())
                img = PIL.Image.open(data)
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

                self.main.bind_all("<Control-s>", self.save)
                self.main.bind_all("<Control-o>", self.load)
                self.names.listbox.bind_all("<<ListboxSelect>>", self.display_card)
                self.main.bind_all("<KP_Add>", self.inc) # "+" from the numeric pad
                self.main.bind_all("<plus>", self.inc) # "+" from the alphabetic pad
                self.main.bind_all("<KP_Subtract>", self.dec) # idem
                self.main.bind_all("<minus>", self.dec)

                self.main.pack(fill="both",expand=True)
                self.names.place(x=0, y=0, anchor="nw", relheight=1.0)
                self.imglbl.place(anchor="ne", relx=1.0, rely=0.0, width=223, height=310)
                self.addacard.place(anchor="se", relx=1.0, rely=1.0)

        def save(self, dummy_arg=None):
                # We should also find a way to store the pictures
                file = asksaveasfile(mode="wb")
                if file is None :
                        return
                pickle.dump(self.cards, file)

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

        def search(self):
                # 1. Ask the card ID (set + number)
                resp = askstring("Ajouter une carte", "Saisissez l'identifiant à 6 caractères en bas à gauche de la carte")
                if resp is None :
                        return
                if not re.match("[A-Z][A-Z0-9]{2}[0-9]{1,3}", resp) :
                        showerror("Saisie incorrecte", "Assurez-vous d'avoir correctement saisi l'identifiant (en respectant la casse)")
                set_id, num = resp[:3], int(resp[3:])

                # 2. Proceed the request
                rq = Card.where(language=LANG, set=set_id, number=num).all()
                if not len(rq) :
                        showerror("Aucune carte trouvée", "Le service distant ne répond pas, ou vérifiez votre saisie")
                        return
                elif len(rq) > 1 :
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


if __name__ == '__main__':
        cp = CardPresenter()
        cp.main.mainloop()
