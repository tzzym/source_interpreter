#include <splashkit.h>
#include "utilities.h"

struct book_data {
	string name;
	string location;
	int page_num;
};

enum menu_type {
	enter_book_details,
	print_book,
	quit
};

book_data reading_book_data() {
	book_data result;
	result.name = read_string("Enter the name of the book: ");
	result.location = read_string("Enter book location: ");
	result.page_num = read_integer("Enter number of pages: ");
	return result;
}

menu_type read_menu() {
	write_line("Menu:");
	menu_type result;

	result = enter_book_details;
	write_line(to_string(result) + " - Enter book details");
	result = print_book;
	write_line(to_string(result) + " - Print book");
	result = quit;
	write_line(to_string(result) + " - Quit");
	
	result = (menu_type)read_integer("Option: ");
	return result;
}

void pro_print_book(book_data book) {
	write_line("Book details: ");
	write_line("Title: " + book.name);
	write_line("Location: " + book.location);
	write_line("Pages: " + to_string(book.page_num));
}

int main() {
	write_line("Book entry system:");
	write_line();
	bool quit_loop = false;
	book_data book = reading_book_data();
	do 
	{
		write_line();
		switch (read_menu())
		 {
		case enter_book_details:
			book = reading_book_data();
			break;
		case print_book: 
			pro_print_book(book);
			break;
        	case quit:
			quit_loop = true;
			break;
		}
	}while(!quit_loop);
	return 0;
}