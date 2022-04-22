from transformers import pipeline


def get_number_of_words(text):
    if len(text) == 0:
        return 0
    word_count = 1
    for character in text:
        if character == ' ':
            word_count += 1
    return word_count


def get_genre():
    genres = ['superhero', 'action', 'drama', 'horror', 'thriller', 'sci_fi']
    print('Please enter your preferred genre from the following options')
    for i in range(len(genres)):
        print('For', genres[i], 'press', str(i))
    input_str = input()
    input_val = int(input_str)
    return genres[input_val]


def truncate_text(text):
    while len(text) > 0 and text[len(text) - 1] != '.':
        text = text[:-1]
    return text


def has_multiple_sentences(text):
    idx = 0
    for character in text:
        if character == '.' and idx >= 10:
            return True
        idx += 1
    return False


def get_truncated_context(prompt_string):
    word_count = get_number_of_words(prompt_string)
    if word_count <= 950:
        return prompt_string
    excess_spaces = word_count - 950
    closing_tag_count = 0
    space_count = 0
    context = ''

    for character in prompt_string:
        if closing_tag_count < 2:
            context += character
        if character == '>':
            closing_tag_count += 1

        if closing_tag_count >= 2:
            if character == ' ':
                space_count += 1

            if space_count >= excess_spaces:
                context += character

    return context


def generate_span(prompt_string, story_gen, min_new_words=50, max_new_words=100):
    previous_word_count = get_number_of_words(prompt_string)
    text = ''
    current_word_count = previous_word_count

    while len(text) == 0 or text[len(text) - 1] != '.' or current_word_count - previous_word_count < min_new_words :
        context = get_truncated_context(prompt_string)
        text_dict = story_gen(context)
        text = text_dict[0]['generated_text']

        current_word_count = get_number_of_words(text)
        if current_word_count - previous_word_count > max_new_words:
            text = truncate_text(text)
        prompt_string = text

    return prompt_string


def get_user_response():
    input_str = input('Do you wish to continue the story? [Y/N]')
    if input_str[0] == 'y' or input_str[0] == 'Y':
        return True
    return False


def get_extra_part(str1, str2):
    extra_portion = ''
    begin = len(str1)
    for idx in range(begin, len(str2)):
        extra_portion += str2[idx]
    return extra_portion


def solicit_user_response(options, passages):
    for _ in range(len(options)):
        print('Option', str(_+1), ':', options[_])

    input_str = input('Which of the above directions would you like the story to progress towards? [1/2/3/4]')
    input_val = int(input_str)
    return passages[input_val-1]


def main():
    story_gen = pipeline("text-generation", "pranavpsv/gpt2-genre-story-generator", max_length=1000)
    summarizer = pipeline("summarization", "sshleifer/distilbart-cnn-12-6")
    prompt_string = "<BOS> <" + get_genre() + ">"
    continue_story = True
    prompt_string = generate_span(prompt_string, story_gen)
    extra_string = ''
    first_time = True
    while continue_story:
        if first_time:
            print(prompt_string)
            first_time=False
        else:
            print(extra_string)
        continue_story = get_user_response()
        if continue_story:
            options = []
            passages = []
            prompt_addition = ['happy happy happy', 'sad sad sad', 'murder murder murder', 'angry angry angry']
            for _ in range(4):
                passage = generate_span(prompt_string+prompt_addition[_], story_gen)
                extra_string = get_extra_part(prompt_string+prompt_addition[_], passage)
                summarized = summarizer(extra_string, min_length=15, max_length=25)
                summary_text = summarized[0]['summary_text']
                if has_multiple_sentences(summary_text):
                    summary_text = truncate_text(summary_text)
                options.append(summary_text)
                passages.append(passage)

            prompt_string = solicit_user_response(options, passages)



if __name__ == '__main__':
    main()
