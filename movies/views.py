from django.shortcuts import render, redirect ,get_object_or_404
from .models import Movie,Theater,Seat,Booking
from django.contrib.auth.decorators import login_required
from urllib.parse import urlparse, parse_qs
from django.utils import timezone
from datetime import timedelta
import re


def movie_list(request):
    search_query=request.GET.get('search')
    if search_query:
        movies=Movie.objects.filter(name__icontains=search_query)
    else:
        movies=Movie.objects.all()
    return render(request,'movies/movie_list.html',{'movies':movies})

def theater_list(request,movie_id):
    movie = get_object_or_404(Movie,id=movie_id)
    theater=Theater.objects.filter(movie=movie)
    return render(request,'movies/theater_list.html',{'movie':movie,'theaters':theater})

def get_movie_youtube_id(url):
    if not url:
        return None
    if 'youtu.be' in url:
        return url.split('/')[-1]
    query = urlparse(url)
    if query.hostname in ['www.youtube.com', 'youtube.com']:
        qs = parse_qs(query.query)
        return qs.get('v', [None])[0]
    return None

def movie_timing(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    trailer_id = get_movie_youtube_id(movie.trailer_url)
    show_timing = Theater.objects.filter(movie=movie).order_by('time')  # Here using Theater model as showtime
    today=timezone.now().date()
    show_timing=Theater.objects.filter(movie=movie,time__date__gte=today).order_by('time')
    return render(request, 'movies/movie_timing.html', {
        'movie': movie,
        'show_timing': show_timing,
        'trailer_id': trailer_id
    })



@login_required(login_url='/login/')
def book_seats(request,theater_id):
    theaters=get_object_or_404(Theater,id=theater_id)
    seats=Seat.objects.filter(theater=theaters)
    def sorting_seats(seat):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', seat.seat_number)]
    seats = sorted(seats, key=sorting_seats)
    for seat in seats:
        if seat.is_seat_reserved and seat.seat_reserved_at:
            if timezone.now() > seat.seat_reserved_at + timedelta(minutes=5):
                seat.is_seat_reserved = False
                seat.seat_reserved_by = None
                seat.seat_reserved_at = None
                seat.save()                                                                    

    if request.method == 'POST':
        selected_seats = request.POST.getlist('seats')
        error_seats = []

        if not selected_seats:
            return render(request, "movies/seat_selection.html", {
                'theater': theaters,
                "seats": seats,
                'error': "No seat selected"
            })
        reserved_ids=[]
        for seat_id in selected_seats:
            seat = get_object_or_404(Seat, id=seat_id, theater=theaters)


            if seat.is_booked or (seat.is_seat_reserved and seat.seat_reserved_by != request.user):
                error_seats.append(seat.seat_number)
                continue

         
            seat.is_seat_reserved = True
            seat.seat_reserved_by = request.user
            seat.seat_reserved_at = timezone.now()
            seat.save()
            reserved_ids.append(seat.id)
        if error_seats:
            error_message = f"The following seats are already booked or reserved: {', '.join(error_seats)}"
            return render(request, 'movies/seat_selection.html', {
                'theater': theaters,
                "seats": seats,
                'error': error_message
            })
        if reserved_ids:
            return redirect('reservation_payment_page', seat_ids=",".join(map(str, reserved_ids)))
        else:
            return render(request, 'movies/seat_selection.html', {
                 'theater': theaters,
                 'seats': seats,
                 'error': "No valid seats could be reserved."
    })    
       

  

    return render(request, 'movies/seat_selection.html', {
        'theater': theaters,
        "seats": seats
    })
@login_required(login_url='/login/')
def reservation_payment_page(request, seat_ids):
    seat_ids = seat_ids.split(',')
    seats = Seat.objects.filter(id__in=seat_ids, seat_reserved_by=request.user)
    if not seats.exists():
       return redirect('home')  # or show error
    theater = seats.first().theater
   

    
    seats_expired = []
    for seat in seats:
        if seat.seat_reserved_at and timezone.now() > seat.seat_reserved_at + timedelta(minutes=5):
            seat.is_seat_reserved = False
            seat.seat_reserved_by = None
            seat.seat_reserved_at = None
            seat.save()
            seats_expired.append(seat.seat_number)

    
    if seats_expired:
        return render(request, 'movies/payment_timeout.html', {
            'seats_expired': seats_expired,
            'theater': theater
        })

    
    if request.method == 'POST':
        for seat in seats:
            seat.is_booked = True
            seat.is_seat_reserved = False
            seat.seat_reserved_by = None
            seat.seat_reserved_at = None
            seat.save()
        return render(request, 'movies/successfully_booked.html', {
            'seats': seats
        })

    
    return render(request, 'movies/reservation_payment_page.html', {
        'seats': seats
        
    })
def timeout_page(request):
    return render(request, 'movies/payment_timeout.html')