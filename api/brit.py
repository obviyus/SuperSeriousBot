from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import telegram
    import telegram.ext

wordlist = {'chips': 'crisps', 'ass': 'arse', 'bubble and squeak': 'greek', 'police station': 'cop-shop', 'overdressed': "dog's dinner", 'paedophiles': 'nonces', 'homosexual': 'botty boy', 'disgusting': "goppin'", 'very drunk': 'legless', 'paedophile': 'nonce', 'pedophiles': 'nonces', 'prositutes': 'pros', 'all right': 'awright', 'wonderful': 'blinder', 'cigarette': 'ciggy', 'ugly girl': 'ding-dong', 'beaten up': 'done over', 'in prison': 'inside', 'exhausted': 'knackered', 'territory': 'manor', 'excellent': 'mint', 'pedophile': 'nonce', 'prositute': 'pro', 'hot chick': 'stunner', 'starving': 'Hank Marvin', 'knickers': 'Alan Whickers', 'violence': 'agro', 'argument': 'barney', 'fighting': 'bovver', 'have sex': 'have a shag', 'terrible': 'chronic', 'bullshit': 'cock and bull', 'definite': 'dred cert', 'went mad': 'went eppy', 'horrible': 'hanging', 'lavatory': 'khazi', 'bathroom': 'khazi', 'nonsense': 'malarkey', 'erection': 'pan handle', 'customer': 'punter', 'believe': 'Adam and Eve', 'trouble': 'grief', 'mistake': 'Cadbury Flake', 'cripple': 'raspberry ripple', 'alright': 'awrght', 'illegal': 'bent as a nine bob note', 'amazing': 'blinder', 'awesome': 'blinder', 'courage': 'bottle', 'gay man': 'queer', 'rubbish': 'cack', 'lesbian': 'carpet muncher', 'cocaine': 'Charlie', 'clothes': 'clobber', 'annoyed': 'hacked off', 'breasts': 'hooters', 'condoms': 'Johnny-bags', 'hookers': 'pros', 'stairs': 'tables and chairs', 'bottle': 'aris', 'pissed': 'Oliver Twist', 'piddle': 'Jimmy Riddle', 'sister': 'skin and blister', 'geezer': 'fridge and freezer', 'stolen': 'bent', 'stoned': 'caned', 'police': 'copper', 'farted': 'dropped one', 'source': 'saahrce', 'hassle': 'grief', 'condom': 'Johnny-bag', 'toilet': 'khazi', 'fed up': 'miffed', 'chilly': 'parky', 'idiots': 'plonkers', 'hooker': 'pro', 'hottie': 'skirt', 'money': 'crust', 'skint': 'boracic lint', 'titty': 'Bristol City', 'balls': 'town halls', 'telly': 'custard and jelly', 'phone': 'dog and bone', 'queer': 'ginger beer', 'pinch': 'half-inch', 'mouth': 'cakehole', 'stink': 'pen and ink', 'curry': 'Ruby Murray', 'snout': 'salmon and trout', 'thief': 'tea leaf', 'Chink': 'Tid', 'state': 'two and eight', 'sleep': 'kip', 'piles': 'Chalfont St Giles', 'toast': 'Holy Ghost', 'darts': 'arras', 'drunk': 'bladdered', 'leave': 'chip', 'happy': 'chuffed', 'blood': 'claret', 'cloth': 'clobber', 'idiot': 'plonker', 'about': 'abaaht', 'other': 'uvver', 'these': 'dese', 'dirty': 'hanging', 'boobs': 'jugs', 'penis': 'John Thomas', 'tired': 'knackered', 'stuff': 'malarkey', 'crazy': 'mental', 'hands': 'mitts', 'cheap': 'naff', 'boner': 'pan handle', 'fools': 'plonkers', 'fight': 'ruck', 'whore': 'slapper', 'real': 'proper', 'arse': 'Khyber Pass', 'wank': 'Jodrell Bank', 'hair': 'Barnet Fair', 'cunt': 'Tristram Hunt', 'time': 'bird lime', 'face': 'boat race', 'look': "butcher's hook", 'mate': 'China plate', 'feet': 'plates of meat', 'road': 'frog and toad', 'piss': 'wazz', 'poof': 'iron hoof', 'soup': 'loop the loop', 'eyes': 'mincers', 'deaf': 'Mutt and Jeff', 'puff': 'Nelly Duff', 'talk': 'rabbit', 'fart': 'blow-off', 'yank': 'septic tank', 'cold': 'parky', 'shit': 'Tom Tit', 'wife': 'missus', 'suit': 'whistle and flute', 'dope': 'Bob Hope', 'dead': 'brown bread', 'draw': 'Dennis Law', 'head': 'loaf of bread', 'geek': 'propellerhead', 'porn': 'bluey', 'homo': 'bum bandit', 'easy': 'cushy', 'both': 'bof', 'more': 'mawer', 'them': "'em", 'been': 'bin', 'than': 'van', 'this': 'dis', 'four': 'faahr', 'with': 'wiv', 'gang': 'firm', 'food': 'nosh', 'boss': 'guv', 'ugly': "goppin'", 'fool': 'plonker', 'nose': 'hooter', 'fuck': 'hump', 'pint': 'jar', 'turd': 'jabby', 'area': 'manor', 'turf': 'manor', 'hand': 'mit', 'kids': 'nippers', 'nerd': 'propellerhead', 'cash': 'readies', 'babe': 'skirt', 'slut': 'slapper', '###': 'melt', 'ass': 'bottle and glass', 'sun': 'currant bun', 'kid': 'nipper', 'wig': 'rug', 'car': 'motahs', 'lie': 'porker', 'tea': 'Rosy Lee', 'cab': 'sherbert', 'hat': 'titfer', 'own': 'Jack Jones', 'sir': 'chief', 'sad': 'choked', 'man': 'John', 'omg': 'crikey', 'the': 'da', 'for': 'fer', 'and': "an'", 'has': "'as", 'poo': 'jabby', 'ear': 'shell-like', 'hoe': 'slapper', 'of': 'ov', 'to': 'ter', 'or': 'awer', '': ''}


def multiple_replace(text):
    result = []
    for word in text.split():
        if word in wordlist:
            word = wordlist[word]
        result.append(word)
    return ' '.join(result)


def brit(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Make text unintelligible"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    text: str

    if not context.args:
        try:
            args: str = message.reply_to_message.text or message.reply_to_message.caption  # type: ignore
            text = multiple_replace(args)
        except AttributeError:
            text = "*Usage:* `/brit {TEXT}`n"
            "*Example:* `/brit Want to watch a movie?`n"
            "Reply with `/brit` to a message to make it unintelligible."
    else:
        text = multiple_replace(' '.join(context.args))

    if message.reply_to_message:
        message.reply_to_message.reply_text(text=text)
    else:
        message.reply_text(text=text)
