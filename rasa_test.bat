@REM Splitting a test set
rasa data split nlu
@REM test nlu
rasa test nlu -u train_test_split/test_data.md