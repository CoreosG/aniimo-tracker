import gc
import tkinter as tk
from tkinter import ttk
import unittest
import weakref

from i18n import Localizer, set_language


class LocalizerRetentionTests(unittest.TestCase):
    def tearDown(self):
        set_language('en')

    def test_repeated_dialogs_release_editable_combo_callbacks_in_both_languages(self):
        for language in ('en','pt-BR'):
            with self.subTest(language=language):
                root=tk.Tk();root.withdraw()
                localizer=Localizer(root,language)
                source=tk.StringVar(root,value='Ready')
                try:
                    localizer.refresh(root);localizer.refresh()
                    commands=set(root.tk.call('info','commands'))
                    retired=[]
                    for _ in range(100):
                        window=tk.Toplevel(root)
                        choice=ttk.Combobox(window,textvariable=source,state='readonly',values=('Ready','Save run'))
                        label=ttk.Label(window,textvariable=source)
                        localizer.refresh(window)
                        retired.append(weakref.ref(choice))
                        window.destroy()
                        del window,choice,label
                    gc.collect();localizer.refresh()
                    self.assertTrue(all(ref() is None for ref in retired))
                    self.assertEqual(source.trace_info(),[])
                    self.assertEqual(set(root.tk.call('info','commands')),commands)
                finally:
                    localizer.close();root.destroy()

    def test_closed_image_dialog_releases_widgets_images_and_variable_traces_in_english(self):
        root=tk.Tk();root.withdraw()
        localizer=Localizer(root,'en')
        source=tk.StringVar(root,value='Ready')
        try:
            localizer.refresh(root);localizer.refresh()
            images=set(root.tk.call('image','names'))
            commands=set(root.tk.call('info','commands'))
            window=tk.Toplevel(root)
            label=ttk.Label(window,textvariable=source);label.pack()
            canvas=tk.Canvas(window);canvas.pack()
            image=tk.PhotoImage(master=root,width=320,height=180)
            canvas.photo=image;canvas.create_image(0,0,image=image)
            localizer.refresh(window)
            self.assertEqual(len(source.trace_info()),1)
            ref=weakref.ref(canvas)
            window.destroy()
            del window,label,canvas,image
            gc.collect()
            localizer.refresh()
            self.assertIsNone(ref(),'Localization must not retain a closed screenshot canvas')
            self.assertEqual(source.trace_info(),[])
            self.assertEqual(set(root.tk.call('image','names')),images)
            self.assertEqual(set(root.tk.call('info','commands')),commands)
        finally:
            localizer.close();root.destroy()
