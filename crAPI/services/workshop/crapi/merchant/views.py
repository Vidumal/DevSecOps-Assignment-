#
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
contains all the views related to Merchant
"""
import logging
import os
from urllib.parse import urlsplit

import requests
from requests.exceptions import MissingSchema, InvalidURL
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from crapi.mechanic.serializers import (
    ServiceCommentViewSerializer,
    ServiceCommentCreateSerializer,
)
from utils.jwt import jwt_auth_required
from utils import messages
from rest_framework.pagination import LimitOffsetPagination
from utils.logging import log_error
from crapi_site import settings
from crapi.mechanic.models import ServiceRequest, ServiceComment
from .serializers import ContactMechanicSerializer, UserServiceRequestSerializer


logger = logging.getLogger()


class ContactMechanicView(APIView):
    """
    View for contact mechanic feature
    """

    @jwt_auth_required
    def post(self, request, user=None):
        """
        contact_mechanic view to call the mechanic api
        :param request: http request for the view
            method allowed: POST
            http request should be authorised by the jwt token of the user
            mandatory fields: ['mechanic_api']
        :param user: User object of the requesting user
        :returns Response object with
            response_from_mechanic_api and 200 status if no error
            message and corresponding status if error
        """
        request_data = request.data
        serializer = ContactMechanicSerializer(data=request_data)
        if not serializer.is_valid():
            log_error(
                request.path,
                request.data,
                status.HTTP_400_BAD_REQUEST,
                serializer.errors,
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        supplied_mechanic_api = request_data.get("mechanic_api", "")
        try:
            parsed_mechanic_api = urlsplit(supplied_mechanic_api)
            supplied_host = parsed_mechanic_api.hostname
        except (TypeError, ValueError):
            supplied_host = None
            parsed_mechanic_api = None

        expected_path = "/workshop/api/mechanic/receive_report"
        if (
            parsed_mechanic_api is None
            or parsed_mechanic_api.scheme not in {"http", "https"}
            or not supplied_host
            or parsed_mechanic_api.username is not None
            or parsed_mechanic_api.password is not None
            or parsed_mechanic_api.path != expected_path
            or parsed_mechanic_api.query
            or parsed_mechanic_api.fragment
        ):
            log_error(
                request.path,
                request.data,
                status.HTTP_400_BAD_REQUEST,
                "Rejected unexpected mechanic API endpoint",
            )
            return Response(
                {"message": "Invalid mechanic API endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Never connect to the host supplied by the client. Route only to this
        # workshop service's fixed report receiver endpoint.
        workshop_port = os.environ.get("SERVER_PORT", "8000")
        if not workshop_port.isdecimal() or not 1 <= int(workshop_port) <= 65535:
            return Response(
                {"message": "Workshop service is misconfigured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        request_url = (
            f"http://127.0.0.1:{workshop_port}"
            "/workshop/api/mechanic/receive_report"
        )
        mechanic_request_data = {
            key: request_data[key]
            for key in ("mechanic_code", "problem_details", "vin")
            if key in request_data
        }

        repeat_request_if_failed = request_data.get("repeat_request_if_failed", False)
        number_of_repeats = request_data.get("number_of_repeats", 1)
        if repeat_request_if_failed and number_of_repeats < 1:
            return Response(
                {"message": messages.MIN_NO_OF_REPEATS_FAILED},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        elif repeat_request_if_failed and number_of_repeats > 100:
            return Response(
                {"message": messages.NO_OF_REPEATS_EXCEEDED},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        repeat_count = 0
        while True:
            logger.info(f"Repeat count: {repeat_count}, mechanic_api: {request_url}")
            try:
                mechanic_response = requests.get(
                    request_url,
                    params=mechanic_request_data,
                    timeout=(3, 10),
                    allow_redirects=False,
                )
                if mechanic_response.status_code == status.HTTP_200_OK:
                    logger.info(f"Got a valid response at repeat count: {repeat_count}")
                    break
                if not repeat_request_if_failed:
                    break
                if repeat_count == number_of_repeats:
                    break
                repeat_count += 1
            except (MissingSchema, InvalidURL) as e:
                log_error(request.path, request.data, status.HTTP_400_BAD_REQUEST, e)
                return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except requests.exceptions.RequestException as e:
                if not repeat_request_if_failed:
                    return Response(
                        {"message": messages.COULD_NOT_CONNECT},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if repeat_count == number_of_repeats:
                    return Response(
                        {"message": messages.COULD_NOT_CONNECT},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                repeat_count += 1
                continue
        mechanic_response_status = mechanic_response.status_code
        try:
            mechanic_response = mechanic_response.json()
        except ValueError:
            mechanic_response = mechanic_response.text
        return Response(
            {
                "response_from_mechanic_api": mechanic_response,
                "status": mechanic_response_status,
            },
            status=mechanic_response_status,
        )


class UserServiceCommentView(APIView):
    """
    View to add a comment to a service request
    """

    @jwt_auth_required
    def get(self, request, user=None, service_request_id=None):
        """
        get all comments for a service request
        """
        service_request = ServiceRequest.objects.get(id=service_request_id)
        if not service_request:
            return Response(
                {"message": messages.NO_OBJECT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        if service_request.vehicle.owner.id != user.id:
            return Response(
                {"message": messages.NO_OBJECT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        comments = ServiceComment.objects.filter(service_request=service_request)
        serializer = ServiceCommentViewSerializer(comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserServiceRequestsView(APIView, LimitOffsetPagination):
    """
    View to return all the service requests
    """

    def __init__(self):
        super(UserServiceRequestsView, self).__init__()
        self.default_limit = settings.DEFAULT_LIMIT

    def get(self, request, vin: str):
        """
        fetch all service requests assigned to the particular mechanic
        :param request: http request for the view
            method allowed: GET
            http request should be authorised by the jwt token of the mechanic
        :param user: User object of the requesting user
        :returns Response object with
            list of service request object and 200 status if no error
            message and corresponding status if error
        """

        service_requests = ServiceRequest.objects.filter(vehicle__vin=vin).order_by(
            "-created_on"
        )
        paginated = self.paginate_queryset(service_requests, request)
        if paginated is None:
            return Response(
                {"message": messages.NO_OBJECT_FOUND},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = UserServiceRequestSerializer(service_requests, many=True)
        response_data = dict(
            service_requests=serializer.data,
            next_offset=(
                self.offset + self.limit
                if self.offset + self.limit < self.count
                else None
            ),
            previous_offset=(
                self.offset - self.limit if self.offset - self.limit >= 0 else None
            ),
            count=self.get_count(paginated),
        )
        return Response(response_data, status=status.HTTP_200_OK)
