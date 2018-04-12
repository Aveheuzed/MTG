#!/usr/bin/env python3

import io, urllib.request, re, pickle, pickletools, zlib, math, zipfile
from PIL import Image, ImageTk
from tkinter.filedialog import askopenfile, asksaveasfile
from tkinter.simpledialog import askstring
from tkinter.messagebox import showerror, askokcancel
from tkinter import tix
from tkinter import LabelFrame # tix one's' buggy...
import mtgsdk

LANG = "French"
SORT_PARAMS = [
        ("nom", "foreign_name"),
        ("coût", "cmc"),
        ("type", "types"),
        ("rareté", "rarity_level")]
RARITY = [
        "Mythic Rare",
        "Rare",
        "Uncommon",
        "Common",
        "Basic Land"]

def list_sets():
        sets = mtgsdk.Set.all()
        vals = [(s.name, s.code) for s in sorted(sets, key=lambda x:x.release_date, reverse=True)]
        return vals

def write_to_file(file, obj):
        obj = pickle.dumps(obj)
        obj = pickletools.optimize(obj)
        obj = zlib.compress(obj)
        file.write(obj)

def read_from_file(file):
        obj = file.read()
        try :
                obj = zlib.decompress(obj) # former versions : the data was stored uncompressed
        except :
                pass
        finally :
                obj = pickle.loads(obj)
                return obj


class ImgCache :
        """Implements an images cache. Please don't make two instances \
        pointing to the same cache file.
        This is a 2-levels cache : one in a zip file, the other in RAM"""

        def __init__(self, filename, maxbuffersize=50):
                self.filename = filename
                try :
                        self.rofh = zipfile.ZipFile(self.filename, mode="r", compression=8)
                except :
                        zipfile.ZipFile(self.filename, mode="x").close()
                        self.rofh = zipfile.ZipFile(self.filename, mode="r")
                self.ramcache = list()
                self.ramindexes = list()
                self.maxbuffersize = maxbuffersize

        def __contains__(self, what) :
                if what in self.ramindexes :
                        return True
                elif what in self.rofh.namelist() :
                        return True
                return False

        def __getitem__(self, what):
                what = str(what)
                if what in self.ramindexes :
                        i = self.ramindexes.index(what)
                        self.ramindexes.insert(0, self.ramindexes.pop(i))
                        self.ramcache.insert(0, self.ramcache.pop(i))
                        return self.ramcache[0]
                elif what in self.rofh.namelist() :
                        if len(self.ramindexes) == self.maxbuffersize :
                                del self.ramindexes[-1]
                                del self.ramcache[-1]
                        self.ramindexes.insert(0, what)
                        self.ramcache.insert(0, Image.open(self.rofh.open(what)))
                        return self.ramcache[0]
                else :
                        raise KeyError("This is not stored yet in this database")

        def __setitem__(self, key, value):
                """Expects a PIL Image for value, and a multiverseid for key"""
                key = str(key)
                if key in self :
                        return
                with zipfile.ZipFile(self.filename, mode="a", compression=8) as rwfh :
                        with rwfh.open(key, mode="w") as file :
                                value.save(file,format=value.format)
                if len(self.ramindexes) == self.maxbuffersize :
                        del self.ramindexes[-1]
                        del self.ramcache[-1]
                self.ramindexes.insert(0, key)
                self.ramcache.insert(0, value)


class Card(mtgsdk.Card) :

        cache = ImgCache("./cache.zip")

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

        def __getattr__(self, attr) :
                """Returns, if present, the name of the card in language LANG.
                Else, returns card.name (usually in English)"""
                if attr not in (
                        "foreign_name",
                        "identifier",
                        "rarity_level"
                        ) :
                        raise AttributeError("No such atribute : "+attr)
                elif attr == "identifier" :
                        return " ".join(str(getattr(self, x, str())).lower() for x in (
                                        "foreign_name",
                                        "subtype",
                                        "type",
                                        "supertype",
                                        "watermark",
                                        "text"))
                elif attr == "rarity_level" :
                        return RARITY.index(self.rarity)
                else : # foreign_name
                        if self.number.endswith("a"):
                                if not hasattr(self, "twin") :
                                        number = self.number[:-1]+"b"
                                        self.twin  = Card.where(set=self.set, number=number).all()[0]
                                return self._get_foreign_name() + " // " + self.twin._get_foreign_name()
                        elif self.number.endswith("b") :
                                if not hasattr(self, "twin") :
                                        number = self.number[:-1]+"a"
                                        self.twin = Card.where(set=self.set, number=number).all()[0]
                                return self.twin._get_foreign_name() + " // " + self._get_foreign_name()
                        else :
                                return self._get_foreign_name()

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
                if str(card.multiverseid) in Card.cache :
                        return ImageTk.PhotoImage(Card.cache[card.multiverseid])
                if card.image_url is None :
                        url = None
                elif card.foreign_names is None :
                        url = card.image_url
                else :
                        url = None
                        for l in card.foreign_names :
                                if l["language"] == LANG :
                                        url = l.get("imageUrl")
                                        break
                        if url is None :
                                url = card.image_url
                if url is not None :
                        data = io.BytesIO(urllib.request.urlopen(url).read())
                        img = Image.open(data)
                else :
                        img = Image.open("./back.jpeg")
                Card.cache[card.multiverseid] = img
                return ImageTk.PhotoImage(img)


class CardPresenter :

        def __init__(self, master=None, cards=list()):
                if master is None :
                        self.main = tix.Tk()
                else :
                        self.main = master
                self.main.resizable(False, True)

                # left part : list of all the cards
                self._cards = list() # for mention only ; self.update fills it
                # self._cards represents all the stored cards
                # self.cards is self._cards after user-filtering
                # see update and below
                self.names = tix.ScrolledListBox(self.main)
                self.names.listbox.configure(width=30, bg="#ffffff")

                # right part : single-card details and picture
                # top : picture
                self.imglbl = tix.Label(self.main)
                self.flipped = False

                # bottom : filters
                self.rightpart = tix.Frame(self.main)

                self.sort = LabelFrame(self.rightpart, text="Trier par : ")
                self.sortby = tix.StringVar(self.sort, "foreign_name")
                self.sort_buttons = list()
                for i, (d,s) in enumerate(SORT_PARAMS) :
                        b = tix.Radiobutton(self.sort, text=d, value=s, variable=self.sortby)
                        b.grid(row=i, column=0, sticky="w")
                        self.sort_buttons.append(b)

                self.filter = LabelFrame(self.rightpart, text="Filtrer :")
                self.filter_query = tix.StringVar(self.filter)
                self.f_e = tix.Entry(self.filter, textvariable=self.filter_query, width=30)

                # buttons to add a card
                self.addacard = tix.Button(self.rightpart, text=" + ", command=self.search)
                self.askcode =  tix.Button(self.rightpart, text=" ? ", command=self.showsets)
                self.set_codes = None

                self.main.bind_all("<Control-s>", self.save)
                self.main.bind_all("<Control-o>", self.load)
                self.names.listbox.bind_all("<<ListboxSelect>>", self.display_card)
                self.main.bind_all("<KP_Add>", self.inc) # "+" from the numeric pad
                self.main.bind_all("<plus>", self.inc) # "+" from the alphabetic pad
                self.main.bind_all("<KP_Subtract>", self.dec) # idem
                self.main.bind_all("<minus>", self.dec)
                self.sortby.trace("w", lambda x,y,z:self.update(self.cards))
                self.filter_query.trace("w", lambda x,y,z:self.update())
                self.imglbl.bind("<Button-1>",self.switch_img)


                self.names.pack(side="left", fill="y")
                self.imglbl.pack(side="top", fill="x")
                self.rightpart.pack(side="top", fill="both", expand=True)
                self.sort.grid(row=0, column=0, sticky="nsew")
                self.f_e.pack()
                self.filter.grid(row=0, column=1, columnspan=3, sticky="nsew")
                self.addacard.grid(row=1, column=3)
                self.askcode.grid(row=1, column=2)
                # these were useful when there was no filter above to fill the place...
                self.rightpart.grid_rowconfigure(0, weight=1)
                self.rightpart.grid_columnconfigure(1, weight=1)

                self.update(cards)

        def save(self, dummy_arg=None):
                # We should also find a way to store the pictures
                file = asksaveasfile(mode="wb")
                if file is None :
                        return
                write_to_file(file, self._cards)
                # we must access _cards directly to get the cards that are hidden by the filter

        def load(self, dummy_arg=None):
                file = askopenfile(mode="rb")
                if file is None :
                        return
                self.update(read_from_file(file))

        def update(self, cards=None):
                """updates the text displayed in self.names, using the filter query.
                If cards is given, that list will be used as self.cards (and will replace it)
                after being sorted.
                No cards, no sorting !"""
                self.selection_reset()
                if cards is not None :
                        self._cards = cards
                        self._cards.sort(key=lambda card:getattr(card, self.sortby.get()))
                self.names.listbox.delete(0,"end")
                self.names.listbox.insert(0,
                        *[card.foreign_name+" (x{})".format(card.amount)*bool(card.amount-1) \
                        for card in self.cards])

        def _get(self):
                fq = self.filter_query.get().strip()
                return [card for card in self._cards if fq in card.identifier]

        cards = property(_get, update)

        def update_one(self, index):
                self.names.listbox.delete(index)
                self.names.listbox.insert(index, self.cards[index].foreign_name+" (x{})".format(self.cards[index].amount)*bool(self.cards[index].amount-1))

        def selection_reset(self):
                self.curimg = ImageTk.PhotoImage(Image.open("./back.jpeg"))
                self.imglbl.configure(image=self.curimg)
                self.curindex = None

        def display_card(self, dummy_arg=None):
                index = self.names.listbox.curselection()
                if not index : return # if no selection
                index = index[0]
                card = self.cards[index]
                self.curimg = card.getimg()
                self.imglbl.configure(image=self.curimg)
                self.curindex = index
                self.flipped = False

        def switch_img(self, dummy_arg=None):
                index = self.names.listbox.curselection()
                if not index : return # if no selection
                index = index[0]
                card = self.cards[index]
                if self.flipped :
                        self.display_card()
                elif hasattr(card,"twin") :
                        self.curimg = Card.getimg(card.twin)
                        self.imglbl.configure(image=self.curimg)
                        self.flipped = True


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

                # if the card's already stored, we can add it manually without request to the remote API
                for i,card in enumerate(self._cards) :
                        if card.set == set_id and card.number == num :
                                self._cards[i] += 1
                                if card in self.cards : #means it's displayed
                                        self.update_one(i)
                                return

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
                self._cards.append(rq)
                self.update(self.cards) # we pass self.cards for parameter, so that update will sort it
                if rq in self.cards :
                        self.names.listbox.select_set(self.cards.index(rq))
                        self.display_card()

        def _select_update(f):
                def f_(self, dummy_arg=None):
                        index = self.names.listbox.curselection()
                        if not index : return
                        index = index[0]
                        card = self.cards[index]

                        if f(self, card) is None : # if f returns something if we don't have to update the selection
                                self.update_one(index)

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
                                index_ = self._cards.index(card)
                                index = self.cards.index(card)
                                del self._cards[index_]
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
