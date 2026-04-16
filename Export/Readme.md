- 指定したフォルダ内は以下の仕様で情報が入っている。
- ファイル名 名前_カテゴリ_連番.png
- お前はこのファイル名から、カテゴリごとに一つのjsonを作成する。
- カテゴリごとにpng内に記載のあるポジティブプロンプトをまとめ、jsonとして吐き出せ。jsonには名前.jsonでよい。
- 上記を実行するpythonプログラムを作成
- ポジティブプロンプトは1行に変換する。
- 重複した文字列は除くため、ignoreのような引数を持つようにしろ。
- デフォルトでは `8k wallpaper, extremely detailed fingers, detail eyes , perfect anatomy, highly detailed background, shiny skin, narrow waist, BREAK` および `1girl, solo , <lora:illyasviel_von_einzbern_(fate_kaleid_liner)_v1:0.8:lbw=OUTD> ,aaillya, long hair, two side up, hair ornament, small breasts, magical girl, cape, yellow ascot, pink dress, sleeveless, detached sleeves, white gloves, white skirt, pink thighhighs
`　を取り除け
- 改行も無視してよい
- ファイルのサンプルは `C:\イラスト関係\成果\002_販売\patreon\202506\イリヤちゃん\0_base` に存在している

```planetext
8k wallpaper, extremely detailed fingers, detail eyes , perfect anatomy, highly detailed background, shiny skin, narrow waist, BREAK
1girl, solo , <lora:illyasviel_von_einzbern_(fate_kaleid_liner)_v1:0.8:lbw=OUTD> ,aaillya, long hair, two side up, hair ornament, small breasts, magical girl, cape, yellow ascot, pink dress, sleeveless, detached sleeves, white gloves, white skirt, pink thighhighs
BREAK
female orgasm, (ecstasy:1.2), saliva trail, tearing up, open clothes, saliva, (heavy breathing:1.2) , sobbing, (heavy breathing:1.2) , tearing up, streaming tears, open mouth, from below , (panties:1.2) , (tentacle wraps around arms:1.1) , (tentacles wraps around legs:1.1) , suspended from tentacles , tearing up ,tentacle-pit ,tentacles, (many many oily tentacles:1.2), (mucus:1.2), <lora:tentacles_v0.4:0.8:lbw=MIDD> , sky , stretching arms , stretching legs , floating in the air , floating body , floating,




Negative prompt: (worst quality, low quality: 1.4), (EasyNegativeV2: 1.1) ,(badhandv4: 1.2) , (bad_prompt_version2: 1.1),(negative_hand - neg:1.4),interlocked fingers: 1.2, locked arms, animal ears, necktie, 4 legs, 3 legs, thighhighs, low quality, worst quality, out of focus, ugly, error, jpeg artifacts, lowers, blurry, bokeh, black bra, black panties, black lingerie, speech bubble, splatoon \\(series\\), splatoon 1, bopoorly_drawn_hands,malformed_hands,missing_limb,floating_limbs,disconnected_limbs,extra_fingers,bad fingers, liquid fingers,poorly drawn fingers,missing fingers, extra digit,fewer digits, ugly open mouth, deformed eyes,partial open mouth, partial head,bad open mouth,inaccurate limb, cropped, too much muscle, (fused digit:1.3), (poorly drawn digit:1.3), (abnormal digit: 1.3), (one hand with more than five digit: 1.1), (too long digit: 1.1), missing digit, (three legs:1.3), (poorly drawn legs:1.3), (fused legs: 1.3), abnormal legs, missing legs, huge thighs, fused shoes, poorly drawn face, blurred background, background without depth, (fused hands:1.3), (poorly drawn hands:1.3), (abnormal hands: 1.3), three hands, missing hands, watermark,signature , multiple views, spoken, cotton bra , cotton panties, (noise: 1.3), (deformed: 1.3), (grayscale: 1.3),(hands poor: 1.2), (fingers poor: 1.2), (bad anatomy: 1.2), (inaccurate limb: 1.2), (extra hands: 1.2),(deformed fingers: 1.2), (extra fingers: 1.2),(long body: 1.2), (long neck: 1.2), (long arm: 1.2), (long leg: 1.2), (extra arms: 1.2), (extra legs: 1.2), (extra navel: 1.2),(ugly), (error), (poorly drawn), (missing), (mutation), (mutated), (liquid body), (bad proportions), (mosaic), (futa),(unnatural pose, color inconsistency, transparency issues, improper proportions, color scheme issues, image seams),(duplicate, morbid, mutilated, bad anatomy, disfigured, signature), bad face, fused face, cloned face, big face, long face, badeyes, fused eyes, poorly drawn eyes, extra eyes, dirty teeth, yellow teeth, black bra , text, black panties , black bow panties , username , artist name, signature, huge breasts , huge body, humpbacked, bad feet , missing arms, bad fingers , huge face , poor quality, retro style , flat shading, flat color , gross, mutated, mutation, bad eyes, bizarre, lacklustre, monochrome, abstract, deformed, glitchy, grotesque, horrifying, malformed, monstrous, repetitive, unnatural, boring, loathesome, poorly drawn, repulsive, strange, ugly , three legs, 3legs , (realistic:1.2),shit, bad, bad proportions, bad shadow, bad anatomy disfigured, bad shoes, bad gloves, bad animal ears, anatomical nonsense, five fingers, simple background, polar lowres, standard quality, bad feet hand finger leg eye, low res, Blurry, Boring, Close-up, Dark(optional), Details are low, Distorted details, Eerie, Foggy (optional), Gloomy (optional), Grains, Grainy, Grayscale (optional), Homogenous, Low contrast, Low quality, Opaque, Overexposed, Oversaturated, Plain, Standard, Surreal, Unattractive, Uncreative, Underexposed , 3D, Absent limbs, Additional appendages, Additional digits, Additional limbs, Altered appendages, Amputee, Asymmetric, Asymmetric ears, Bad anatomy, Bad ears, Bad eyes, Bad face, Bad proportions, Beard (optional), Broken finger, Broken hand, Broken leg, Broken wrist, Cartoon, Childish (optional), Cloned face, Cloned head, Collapsed eyeshadow, Combined appendages, Conjoined, Copied visage, Corpse, Cripple, Cropped head, Cross-eyed, Depressed, Desiccated, Disconnected limb, Disfigured, Dismembered, Disproportionate, Double face, Duplicated features, Eerie, Elongated throat , (splatoon \(series\), splatoon 1, splatoon 2, splatoon 3:1.4)
Steps: 60, Sampler: DPM++ 3M SDE Exponential, CFG scale: 9, Seed: 1104858523, Size: 512x768, Model hash: a74567abc1, Model: anyMyCuriusAbyssMeina, VAE hash: 54b156d6ce, VAE: ClearVAE_V2.2.safetensors, Denoising strength: 0.55, Clip skip: 2, Hires upscale: 2, Hires steps: 20, Hires upscaler: 4x_fatal_Anime_500000_G, Lora hashes: "illyasviel_von_einzbern_(fate_kaleid_liner)_v1: 4fec2bab7d3b, tentacles_v0.4: e0f5ac74a932", TI hashes: "EasyNegativeV2: 339cc9210f70, badhandv4: 5e40d722fc3d", Version: v1.6.0
```


  {
    "category": "01",
    "prompt": [
        "C,B,A",
        "B,A,C"
    ]
  }

  この場合

  
  {
    "category": "01",
    "prompt": [
        "A,B,C",
        "A,B,C"
    ]
  }


    "arched back, bukkake, close-up pussy, close-up pussy, cum on body, ecstasy, from below, heavy breathing, large insertion, legs up, nipples, open mouth, pussy, pussy juice, restrained, sex, speech bubble, spread legs, sweat, x-ray",
      "ass, bukkake, clenched teeth, close-up pussy, cum on body, doggystyle, ecstasy, from behind, from below, half-closed eyes, heavy breathing, large insertion, pussy juice, restrained, sex, speech bubble, sweat",
      "arched back, bukkake, close-up pussy, close-up pussy, cum on body, ecstasy, heavy breathing, large insertion, open mouth, pussy, pussy juice, restrained, sex, speech bubble, sweat, sweat, top-down bottom-up from behind",
  
  修正後
      "arched back, bukkake, close-up pussy, close-up pussy, cum on body, ecstasy, from below, heavy breathing, large insertion, legs up, nipples, open mouth, pussy, pussy juice, restrained, sex, speech bubble, spread legs, sweat, x-ray",
      "arched back, bukkake, close-up pussy, close-up pussy, cum on body, ecstasy, heavy breathing, large insertion, open mouth, pussy, pussy juice, restrained, sex, speech bubble, sweat, sweat, top-down bottom-up from behind",
      "ass, bukkake, clenched teeth, close-up pussy, cum on body, doggystyle, ecstasy, from behind, from below, half-closed eyes, heavy breathing, large insertion, pussy juice, restrained, sex, speech bubble, sweat",
  